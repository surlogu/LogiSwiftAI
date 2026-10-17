import pandas as pd
import streamlit as st
from datetime import time

from engine import CITIES, add_shipment, assign_driver, connect, driver_records, sample_shipments, shipment_workflows, start_trip, report_driver_update
from gemini_analysis import recommend_options
from ui_common import api_key, configure_page


configure_page('Ops Console | LogiSwift AI', '🏭')
st.title('🏭 Operations Console')
st.caption('Create shipments, assign available drivers, and run the repeatable breakdown demo.')
conn = connect()

with st.expander('Create a shipment', expanded=True):
    with st.form('ops_create_shipment', clear_on_submit=True):
        vendor = st.text_input('Vendor name', value='Demo Vendor')
        a,b,c = st.columns(3)
        with a: origin = st.selectbox('Pickup city', CITIES, key='ops_origin')
        with b: destination = st.selectbox('Drop city', CITIES, index=1, key='ops_destination')
        with c: priority = st.selectbox('Priority', ['Normal','High'])
        d,e=st.columns(2)
        with d: deadline=st.time_input('Delivery deadline',value=time(18,0),step=300).strftime('%H:%M')
        with e: package_type=st.selectbox('Package type',['general','electronics','fragile','food','medical','documents'])
        create = st.form_submit_button('Create shipment', use_container_width=True)
    if create:
        try:
            shipment_id = add_shipment(origin, destination, priority, 'Normal', vendor, conn, deadline, package_type)
            st.success(f'Created {shipment_id}: {origin} → {destination}.')
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

st.subheader('Assign a driver')
workflows = shipment_workflows(conn)
if workflows:
    lookup = {row['Shipment']:row for row in workflows}
    assignable = [row for row in workflows if row['Lifecycle'] in ('CREATED','DRIVER_ASSIGNED')]
    available = driver_records(conn, available_only=True)
    if assignable and available:
        left,right = st.columns([2,2])
        with left: shipment_id = st.selectbox('Shipment', [r['Shipment'] for r in assignable], format_func=lambda sid:f"{sid} · {lookup[sid]['Origin']} → {lookup[sid]['Destination']}")
        with right: driver_id = st.selectbox('Available driver', [d['driver_id'] for d in available], format_func=lambda did: next(f"{d['name']} · {d['vehicle']} · reliability {d['reliability']:.0%}" for d in available if d['driver_id']==did))
        if st.button('Assign selected driver', type='primary', use_container_width=True):
            try:
                assign_driver(shipment_id,driver_id,conn)
                st.success('Driver assigned. The driver can now start the trip on the Driver App page.')
                st.rerun()
            except ValueError as exc: st.error(str(exc))
    elif not assignable:
        st.info('All current shipments have moved past the assignment step.')
    else:
        st.info('No available drivers. Complete or reassign another active trip first.')
else:
    st.info('Create a shipment to start the workflow.')

st.subheader('One-click deterministic demo')
st.write('Creates a shipment, assigns the first demo driver, starts its trip, reports a breakdown, and lets the recovery agent reassign it.')
if st.button('▶ Create and run breakdown demo',use_container_width=True):
    try:
        demo_id=add_shipment('Chennai','Bengaluru','High','Normal','Demo Vendor',conn)
        available=driver_records(conn,available_only=True)
        if len(available)<2:
            raise ValueError('At least two drivers must be available. Complete another active shipment first.')
        original=next((d for d in available if d['driver_id']=='DRIVER_A'),available[0])
        assign_driver(demo_id,original['driver_id'],conn)
        start_trip(demo_id,original['driver_id'],conn)
        report_driver_update(demo_id,original['name'],'Vehicle breakdown',conn,'Demo: vehicle will not start near the pickup route.')
        current=next(r for r in shipment_workflows(conn) if r['Shipment']==demo_id)
        opts=current['Recommendations']
        ai_options,diagnostic=recommend_options('Vehicle breakdown',demo_id,opts,api_key('GEMINI_API_KEY'))
        from engine import save_recommendations
        save_recommendations(demo_id,ai_options,conn)
        st.session_state['last_breakdown_demo']=demo_id
        st.success(f"Demo complete: {demo_id} was reassigned to {current['Driver']}. Open Agent Control Tower to inspect or change the recovery.")
        if diagnostic: st.caption(diagnostic)
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))

if workflows:
    st.subheader('Shipment board')
    display=pd.DataFrame(workflows)
    st.dataframe(display[['Shipment','Vendor','Origin','Destination','Deadline','Package','Priority','Status','Lifecycle','Driver','Vehicle','Issue','Agent status']],use_container_width=True,hide_index=True)

st.subheader('Driver availability')
st.dataframe(pd.DataFrame(driver_records(conn)),use_container_width=True,hide_index=True)
conn.close()
