import pandas as pd
import streamlit as st

from engine import connect, history, shipment_workflows
from ui_common import configure_page


configure_page('LogiSwift AI | Control Tower', '🚚')
st.title('🚚 LogiSwift AI')
st.caption('Autonomous shipment recovery demo · shared SQLite workflow · Streamlit multipage app')
st.markdown('Use the separate pages in the left sidebar to act as **Operations**, **Driver**, or **Agent Control Tower**. Each screen reads and updates the same shipment records.')

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
st.write('In Ops Console, click **Create and run breakdown demo**. It creates and assigns a shipment, starts the trip, reports a vehicle breakdown, and applies the first safe replacement-driver recommendation. Then inspect or change the driver in Agent Control Tower, continue the trip in Driver App, and mark it delivered.')
if incidents:
    st.caption(f"{len(incidents)} deterministic simulation incident(s) are in the audit history. Gemini recommendations are optional and never execute actions on their own.")
conn.close()
