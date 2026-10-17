import pandas as pd
import streamlit as st
from datetime import time

from engine import (
    CITIES,
    VEHICLES,
    add_shipment,
    approve_recommendation,
    assign_driver,
    connect,
    decision_history,
    driver_records,
    has_decision_feedback,
    rank_options_from_feedback,
    reject_recommendation,
    save_recommendations,
    shipment_workflows,
    start_trip,
    report_driver_update,
)
from gemini_analysis import recommend_options
from maps_view import show_shipment_map
from ui_common import api_key, configure_page


configure_page('Ops Console | LogiSwift AI', '🏭')
st.title('🏭 Operations Console')
st.caption('Choose a tab for shipment setup, recovery approval, or fleet monitoring.')
conn = connect()

create_tab, recovery_tab, monitor_tab = st.tabs([
    '📦 Create & assign',
    '🧠 Recovery approvals',
    '🚚 Shipment monitor',
])

with create_tab:
    st.subheader('Create a shipment')
    with st.form('ops_create_shipment', clear_on_submit=True):
        vendor = st.text_input('Vendor name', value='Demo Vendor')
        a, b, c = st.columns(3)
        with a:
            origin = st.selectbox('Pickup city', CITIES, key='ops_origin')
        with b:
            destination = st.selectbox('Drop city', CITIES, index=1, key='ops_destination')
        with c:
            priority = st.selectbox('Priority', ['Normal', 'High'])
        d, e = st.columns(2)
        with d:
            deadline = st.time_input('Delivery deadline', value=time(18, 0), step=300).strftime('%H:%M')
        with e:
            package_type = st.selectbox('Package type', ['general', 'electronics', 'fragile', 'food', 'medical', 'documents'])
        create = st.form_submit_button('Create shipment', use_container_width=True)
    if create:
        try:
            shipment_id = add_shipment(origin, destination, priority, 'Normal', vendor, conn, deadline, package_type)
            st.success(f'Created {shipment_id}: {origin} → {destination}.')
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    st.divider()
    st.subheader('Assign an available driver')
    workflows = shipment_workflows(conn)
    assignable = [row for row in workflows if row['Lifecycle'] in ('CREATED', 'DRIVER_ASSIGNED')]
    available = driver_records(conn, available_only=True)
    if assignable and available:
        left, right = st.columns(2)
        with left:
            shipment_id = st.selectbox(
                'Shipment',
                [row['Shipment'] for row in assignable],
                format_func=lambda sid: next(
                    f"{row['Shipment']} · {row['Origin']} → {row['Destination']}"
                    for row in assignable if row['Shipment'] == sid
                ),
            )
        with right:
            driver_id = st.selectbox(
                'Available driver',
                [driver['driver_id'] for driver in available],
                format_func=lambda did: next(
                    f"{driver['name']} · {driver['vehicle']} · reliability {driver['reliability']:.0%}"
                    for driver in available if driver['driver_id'] == did
                ),
            )
        if st.button('Assign selected driver', type='primary', use_container_width=True):
            try:
                assign_driver(shipment_id, driver_id, conn)
                st.success('Driver assigned. They can start the trip in Driver App.')
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    elif not assignable:
        st.info('No shipments are waiting for driver assignment. Create one above to begin.')
    else:
        st.info('No drivers are available. Complete an active trip or approve a recovery first.')

    st.divider()
    st.subheader('Guided breakdown demo')
    st.write('Creates a sample shipment, starts its trip, and submits a simulated breakdown. The replacement driver stays unchanged until Ops approves a recovery.')
    if st.button('▶ Create and run breakdown demo', use_container_width=True):
        try:
            available = driver_records(conn, available_only=True)
            if len(available) < 2:
                raise ValueError('At least two drivers must be available. Complete another active shipment first.')
            demo_id = add_shipment('Chennai', 'Bengaluru', 'High', 'Normal', 'Demo Vendor', conn, is_demo=True)
            original = next((driver for driver in available if driver['driver_id'] == 'DRIVER_A'), available[0])
            assign_driver(demo_id, original['driver_id'], conn)
            start_trip(demo_id, original['driver_id'], conn)
            report_driver_update(demo_id, original['name'], 'Vehicle breakdown', conn, 'Demo: vehicle will not start near the pickup route.')
            current = next(row for row in shipment_workflows(conn) if row['Shipment'] == demo_id)
            options = current['Recommendations']
            if has_decision_feedback('Vehicle breakdown', conn):
                ranked = rank_options_from_feedback('Vehicle breakdown', options, conn)
                diagnostic = 'Gemini skipped; prior Ops decisions ranked these suggestions locally.'
            else:
                ranked, diagnostic = recommend_options('Vehicle breakdown', demo_id, options, api_key('GEMINI_API_KEY'))
            save_recommendations(demo_id, ranked, conn)
            st.success(f'{demo_id} is waiting in Recovery approvals. No replacement driver has been assigned yet.')
            if diagnostic:
                st.caption(diagnostic)
        except ValueError as exc:
            st.error(str(exc))

with recovery_tab:
    st.subheader('Review and approve agent recommendations')
    st.caption('Accept applies the selected recovery. Reject records your reason and advances to the next option. The shipment is unchanged until you accept.')
    pending_items = [row for row in shipment_workflows(conn) if row['Lifecycle'] == 'AWAITING_APPROVAL']
    available_driver_ids = {driver['driver_id'] for driver in driver_records(conn, available_only=True)}
    if not pending_items:
        st.info('There are no recovery recommendations waiting for review.')
    for item in pending_items:
        options = [
            option for option in item['Recommendations']
            if option.get('review_status', 'PENDING') == 'PENDING'
            and (not option.get('driver_id') or option['driver_id'] in available_driver_ids)
        ]
        if not options:
            st.warning(f"{item['Shipment']}: no eligible recovery option is currently available. A replacement driver already assigned elsewhere is hidden; review again when a driver becomes available.")
            continue
        current_id = item['Current recommendation ID']
        current = next((option for option in options if option['id'] == current_id), options[0])
        with st.expander(f"{item['Shipment']} · {item['Issue']} · approval required", expanded=True):
            st.markdown(f"**Current suggestion:** {current['action']}")
            st.write(current.get('reason', ''))
            st.caption(f"{current.get('source', 'Rules-based')} · {len(options)} option(s) available")
            if item['Issue'] == 'Traffic delay':
                st.markdown('**Traffic-aware road route comparison**')
                maps_key = api_key('GOOGLE_MAPS_API_KEY')
                if maps_key:
                    show_shipment_map(item, maps_key, height=560)
                    st.caption('Compare Google route estimates, then accept or reject one of the agent recommendations below.')
                else:
                    st.warning('Set GOOGLE_MAPS_API_KEY to show road routes here. You can still review the recovery options.')
            with st.form(f"ops_review_{item['Shipment']}"):
                pending_ids = [option['id'] for option in options]
                selected_id = st.selectbox(
                    'Suggestion to approve',
                    pending_ids,
                    index=pending_ids.index(current['id']),
                    format_func=lambda oid: next(option['action'] for option in options if option['id'] == oid),
                )
                selected = next(option for option in options if option['id'] == selected_id)
                driver_id = selected.get('driver_id')
                replacement_options = [option for option in options if option.get('driver_id')]
                if selected_id.startswith('replace:') and replacement_options:
                    driver_ids = [option['driver_id'] for option in replacement_options]
                    default_driver = selected.get('driver_id')
                    available_drivers = driver_records(conn)
                    driver_id = st.selectbox(
                        'Replacement driver',
                        driver_ids,
                        index=driver_ids.index(default_driver),
                        format_func=lambda did: next(
                            f"{driver['name']} · {driver['vehicle']} · reliability {driver['reliability']:.0%}"
                            for driver in available_drivers if driver['driver_id'] == did
                        ),
                    )
                current_vehicle = selected.get('vehicle') or item['Vehicle'] or VEHICLES[0]
                vehicle = st.selectbox('Vehicle', VEHICLES, index=VEHICLES.index(current_vehicle) if current_vehicle in VEHICLES else 0)
                rejection_reason = st.text_input('Reason if rejecting', placeholder='Optional: unsafe route, unavailable vehicle, ETA too high…')
                driver_message = st.text_input('Message to driver', placeholder='Example: Stay at the safe location; Ops is arranging the alternate route.')
                yes, no = st.columns(2)
                with yes:
                    accept = st.form_submit_button('✓ Accept and apply', type='primary', use_container_width=True)
                with no:
                    reject = st.form_submit_button(f"✕ Reject current suggestion: {current['action']}", use_container_width=True)
            if accept:
                try:
                    chosen_id = f"replace:{driver_id}" if selected_id.startswith('replace:') else selected_id
                    approve_recommendation(item['Shipment'], chosen_id, driver_id, vehicle, conn, driver_message=driver_message)
                    st.success('Approval recorded, recovery applied, and the message saved for the assigned driver.')
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if reject:
                try:
                    next_option = reject_recommendation(item['Shipment'], current['id'], rejection_reason, conn, driver_message=driver_message)
                    if next_option:
                        st.info(f"Rejection recorded. Next suggestion: {next_option['action']}.")
                    else:
                        st.warning('All recommendations were rejected. The shipment is escalated for human review.')
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with st.expander('Approval and rejection history'):
        decisions = decision_history(conn=conn)
        if decisions:
            st.dataframe(pd.DataFrame(decisions), use_container_width=True, hide_index=True)
        else:
            st.caption('Accepted and rejected suggestions will appear here and influence future rankings.')

with monitor_tab:
    workflows = shipment_workflows(conn)
    st.subheader('Shipment board')
    if workflows:
        display = pd.DataFrame(workflows)
        st.dataframe(
            display[['Shipment', 'Vendor', 'Origin', 'Destination', 'Deadline', 'Package', 'Priority', 'Status', 'Lifecycle', 'Driver', 'Vehicle', 'Issue', 'Agent status']],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info('No shipments yet. Create a shipment in the first tab.')
    st.info('Open **Driver Roster** in the sidebar to see driver availability. Only available drivers appear as recovery replacements.')

conn.close()
