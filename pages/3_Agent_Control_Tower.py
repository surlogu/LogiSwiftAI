import pandas as pd
import streamlit as st

from engine import connect, decision_history, shipment_workflows, workflow_events
from ui_common import configure_page


configure_page('Agent Control Tower | LogiSwift AI', '⚡')
st.title('⚡ Agent Control Tower')
st.caption('View the agent’s reasoning, suggestions, approval state, and audit history. Recovery actions require Ops approval.')
conn=connect()
workflows=shipment_workflows(conn)
incidents=[row for row in workflows if row['Issue'] and row['Issue']!='No issue']
if not incidents:
    st.info('No driver issues yet. Use the Driver App, or run the one-click breakdown demo in Ops Console.')
else:
    choices=[row['Shipment'] for row in incidents]
    selected_id=st.selectbox('Shipment incident',choices,format_func=lambda sid:next(f"{row['Shipment']} · {row['Issue']} · {row['Lifecycle']}" for row in incidents if row['Shipment']==sid))
    item=next(row for row in incidents if row['Shipment']==selected_id)
    st.subheader(f"{item['Shipment']} · {item['Origin']} → {item['Destination']}")
    reporting_driver=item['Previous Driver ID'] or item['Driver'] or 'Unknown'
    st.write(f"Issue: **{item['Issue']}** · Reporting driver: **{reporting_driver}** · State: **{item['Lifecycle']}**")
    if item['Issue description']:
        st.info(item['Issue description'])

    if item['Lifecycle']=='AWAITING_APPROVAL':
        current=next((option for option in item['Recommendations'] if option['id']==item['Current recommendation ID']),None)
        if current:
            st.warning(f"Waiting for Ops approval. Current suggestion: **{current['action']}** — {current.get('reason','')}")
        st.info('Open Ops Console to accept a suggestion or reject it and review the next option. No driver or route is changed before approval.')
    elif item['Vendor decision']=='Approved':
        st.success(f"Ops approved: {item['Selected action']}. The decision was applied to shipment {item['Shipment']}.")
    elif item['Lifecycle']=='ESCALATED_TO_HUMAN':
        st.error('The agent has no approved safe recovery. This shipment is escalated for human review.')

    if item['Recommendations']:
        st.markdown('### Candidate recommendations')
        for option in item['Recommendations']:
            state=option.get('review_status','PENDING')
            status_label={'APPROVED':'✅ Ops approved','REJECTED':'✕ Ops rejected','NOT_SELECTED':'Not selected'}.get(state,'Waiting for Ops')
            st.markdown(f"**{option.get('rank','?')}. {option['action']}** · {status_label}")
            st.caption(f"{option.get('source','Rules-based')} — {option.get('reason','')}")
            if option.get('rejection_reason'):
                st.caption(f"Ops rejection reason: {option['rejection_reason']}")

    st.markdown('### Shipment decision events')
    events=workflow_events(conn,selected_id)
    if events:
        st.dataframe(pd.DataFrame(events),use_container_width=True,hide_index=True)
    else:
        st.info('No decision events recorded yet.')

st.markdown('### Historical Ops approvals and rejections')
decisions=decision_history(conn=conn)
if decisions:
    st.dataframe(pd.DataFrame(decisions),use_container_width=True,hide_index=True)
else:
    st.caption('Ops decisions will appear here and influence future rankings locally.')
conn.close()
