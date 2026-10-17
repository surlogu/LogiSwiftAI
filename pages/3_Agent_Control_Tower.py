import pandas as pd
import streamlit as st

from engine import VEHICLES, connect, driver_records, select_recovery, shipment_workflows, workflow_events
from ui_common import configure_page


configure_page('Agent Control Tower | LogiSwift AI', '⚡')
st.title('⚡ Agent Control Tower')
st.caption('Review ranked recovery choices, change the driver or vehicle, and inspect each state transition.')
conn=connect()
workflows=shipment_workflows(conn)
incidents=[r for r in workflows if r['Issue'] and r['Issue']!='No issue']
if not incidents:
    st.info('No driver issues yet. Use the Driver App, or run the one-click breakdown demo in Ops Console.')
else:
    choices=[r['Shipment'] for r in incidents]
    selected_id=st.selectbox('Incident shipment',choices,format_func=lambda sid: next(f"{r['Shipment']} · {r['Issue']} · {r['Lifecycle']}" for r in incidents if r['Shipment']==sid))
    item=next(r for r in incidents if r['Shipment']==selected_id)
    st.subheader(f"{item['Shipment']} · {item['Origin']} → {item['Destination']}")
    st.write(f"Issue: **{item['Issue']}** · Previous driver: **{item['Driver'] or 'Unknown'}** · Current lifecycle: **{item['Lifecycle']}**")
    if item['Issue description']: st.info(item['Issue description'])
    options=item['Recommendations']
    if options:
        st.markdown('### Ranked recovery options')
        for option in options:
            st.markdown(f"**{option.get('rank','?')}. {option['action']}** — {option.get('reason','')}")
            st.caption(f"{option.get('source','Rules-based')} · option ID `{option['id']}`")
        option_ids=[o['id'] for o in options]
        default_action=item['Selected action']
        default_idx=next((i for i,o in enumerate(options) if o['id']==default_action or o['action']==default_action),0)
        with st.form(f"choose_recovery_{selected_id}"):
            action_id=st.selectbox('Choose the recovery (you can change the agent choice)',option_ids,index=default_idx,format_func=lambda oid:next(f"{o.get('rank')}. {o['action']}" for o in options if o['id']==oid))
            selected=next(o for o in options if o['id']==action_id)
            replace_options=[o for o in options if o['id'].startswith('replace:')]
            driver_id=selected.get('driver_id')
            if selected['id'].startswith('replace:'):
                driver_id=st.selectbox('Replacement driver', [o['driver_id'] for o in replace_options],index=next((i for i,o in enumerate(replace_options) if o['id']==action_id),0),format_func=lambda did:next(f"{d['name']} · {d['vehicle']} · reliability {d['reliability']:.0%}" for d in driver_records(conn) if d['driver_id']==did))
            current_vehicle=selected.get('vehicle') or item['Vehicle'] or VEHICLES[0]
            vehicle=st.selectbox('Vehicle to assign',VEHICLES,index=VEHICLES.index(current_vehicle) if current_vehicle in VEHICLES else 0)
            apply=st.form_submit_button('Apply selected recovery',type='primary',use_container_width=True)
        if apply:
            try:
                chosen_id=f"replace:{driver_id}" if action_id.startswith('replace:') else action_id
                select_recovery(selected_id,chosen_id,driver_id,vehicle,conn)
                st.success('Recovery choice saved. Shipment ID stays the same; the Driver App now reflects the chosen driver and vehicle.')
                st.rerun()
            except ValueError as exc: st.error(str(exc))
    else:
        st.warning('No safe candidate is available; dispatcher review is required.')
    st.markdown('### Recovery and audit events')
    events=workflow_events(conn,selected_id)
    if events: st.dataframe(pd.DataFrame(events),use_container_width=True,hide_index=True)
    else: st.info('No workflow events recorded yet.')

st.markdown('### Current incident queue')
st.dataframe(pd.DataFrame(incidents)[['Shipment','Issue','Lifecycle','Agent status','Agent decision','Vendor decision','Driver','Vehicle']],use_container_width=True,hide_index=True)
conn.close()
