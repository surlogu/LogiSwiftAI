import pandas as pd
import streamlit as st

from engine import DRIVER_ISSUES, connect, driver_records, report_driver_update, shipment_workflows, start_trip, complete_delivery, save_recommendations
from gemini_analysis import recommend_options
from ui_common import api_key, configure_page


configure_page('Driver App | LogiSwift AI', '🚚')
st.title('🚚 Driver App')
st.caption('Each driver has a separate screen. Select the demo driver, start their assigned trip, report an issue, then complete delivery after recovery.')
conn=connect()
drivers=driver_records(conn)
driver_names={d['driver_id']:d['name'] for d in drivers}
driver_id=st.selectbox('Signed-in driver (simulation)',[d['driver_id'] for d in drivers],format_func=lambda did:f"{driver_names[did]} · {did}")
workflows=shipment_workflows(conn)
assigned=[r for r in workflows if r['Driver ID']==driver_id and r['Lifecycle'] not in ('DELIVERED','ESCALATED_TO_HUMAN')]

if not assigned:
    st.info('No active shipment is assigned to this driver. Assign one in Ops Console or use the one-click demo.')
else:
    for item in assigned:
        st.divider()
        st.subheader(f"Shipment {item['Shipment']}")
        st.write(f"**{item['Origin']} → {item['Destination']}** · {item['Package']} · deadline {item['Deadline']} · {item['Priority']} priority")
        st.write(f"Vehicle: **{item['Vehicle'] or 'Not assigned'}** · Lifecycle: **{item['Lifecycle']}**")
        if item['Lifecycle'] in ('DRIVER_ASSIGNED','DRIVER_REASSIGNED','RECOVERY_APPROVED'):
            if st.button('▶ Start trip',key=f"start_{item['Shipment']}",type='primary',use_container_width=True):
                try: start_trip(item['Shipment'],driver_id,conn); st.rerun()
                except ValueError as exc: st.error(str(exc))
        if item['Lifecycle']=='IN_TRANSIT':
            with st.form(f"issue_{item['Shipment']}"):
                issue=st.selectbox('Report an issue', [key for key in DRIVER_ISSUES if key!='No issue'],key=f"issue_type_{item['Shipment']}")
                description=st.text_area('Describe the issue and current location',placeholder='For example: vehicle will not start near Adyar bridge.',key=f"issue_note_{item['Shipment']}")
                submit=st.form_submit_button('Submit issue to recovery agent',use_container_width=True)
            if submit:
                try:
                    report_driver_update(item['Shipment'],driver_names[driver_id],issue,conn,description)
                    updated=next(r for r in shipment_workflows(conn) if r['Shipment']==item['Shipment'])
                    options,diagnostic=recommend_options(issue,item['Shipment'],updated['Recommendations'],api_key('GEMINI_API_KEY'))
                    save_recommendations(item['Shipment'],options,conn)
                    if diagnostic: st.session_state[f"recommendation_info_{item['Shipment']}"]=diagnostic
                    st.success(f"Issue recorded for {item['Shipment']}. Agent recovery options are available in the Control Tower.")
                    st.rerun()
                except ValueError as exc: st.error(str(exc))
        if item['Lifecycle']=='IN_TRANSIT':
            if st.button('✓ Mark delivered',key=f"deliver_{item['Shipment']}",use_container_width=True):
                try: complete_delivery(item['Shipment'],driver_id,conn); st.success('Delivery completed and driver marked available.'); st.rerun()
                except ValueError as exc: st.error(str(exc))
        if item['Lifecycle']=='DRIVER_REASSIGNED':
            st.success('This is the replacement driver on the original shipment. Start the trip, then mark it delivered when complete.')
        diagnostic=st.session_state.get(f"recommendation_info_{item['Shipment']}")
        if diagnostic: st.caption(diagnostic)

st.subheader('Assigned shipment history')
mine=[r for r in workflows if r['Driver ID']==driver_id]
if mine:
    st.dataframe(pd.DataFrame(mine)[['Shipment','Origin','Destination','Lifecycle','Issue','Agent decision','Vehicle']],use_container_width=True,hide_index=True)
conn.close()
