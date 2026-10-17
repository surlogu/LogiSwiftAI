import pandas as pd
import streamlit as st

from engine import connect, history, shipment_workflows
from ui_common import configure_page


configure_page('LogiSwift AI | Control Tower', '🚚')
st.title('🚚 LogiSwift AI')
st.caption('Autonomous shipment recovery demo · shared SQLite workflow · Streamlit multipage app')
st.markdown('Use the left sidebar to open **Ops Console** for shipment setup and approvals, **Driver App** for trip updates, **Agent Control Tower** for the audit trail, or **Road Routes** to compare routes.')

conn=connect()
shipments=shipment_workflows(conn)
incidents=history(conn)
delivered=sum(item['Lifecycle']=='DELIVERED' for item in shipments)
reassigned=sum(item['Lifecycle']=='DRIVER_REASSIGNED' for item in shipments)
reported=sum(bool(item['Issue'] and item['Issue']!='No issue') for item in shipments)
a,b,c,d=st.columns(4)
a.metric('Shipments',len(shipments))
b.metric('Issues reported',reported)
c.metric('Drivers reassigned',reassigned)
d.metric('Delivered',delivered)

st.subheader('Current shipment board')
if shipments:
    board=pd.DataFrame(shipments)
    st.dataframe(board[['Shipment','Vendor','Origin','Destination','Deadline','Package','Status','Lifecycle','Driver','Vehicle','Issue','Agent decision']],use_container_width=True,hide_index=True)
else:
    st.info('No vendor shipments have been created yet. Open Ops Console to add one.')

st.subheader('Quick demo')
st.write('In Ops Console → **Create & assign**, click **Create and run breakdown demo**. Then open **Recovery approvals** and accept or reject the suggestion. The Agent Control Tower shows the audit trail; the replacement driver continues the trip in Driver App after Ops approval.')
if incidents:
    st.caption(f"{len(incidents)} deterministic simulation incident(s) are in the audit history. Gemini recommendations are optional and never execute actions on their own.")
conn.close()
