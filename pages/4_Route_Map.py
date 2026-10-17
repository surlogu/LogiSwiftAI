import os
import streamlit as st

from engine import connect, sample_shipments
from maps_view import show_shipment_map
from ui_common import api_key, configure_page


configure_page('Road Routes | LogiSwift AI', '🗺️')
st.title('🗺️ Real road routes')
st.caption('Google computes driving roads and optional alternate routes between the shipment’s city endpoints. This is route planning, not live vehicle tracking.')
conn=connect()
shipments=sample_shipments(conn)
if not shipments:
    st.info('Create a shipment in Ops Console first.')
else:
    shipment_id=st.selectbox('Shipment', [item['Shipment'] for item in shipments],format_func=lambda sid:next(f"{s['Shipment']} · {s['Origin']} → {s['Destination']}" for s in shipments if s['Shipment']==sid))
    shipment=next(s for s in shipments if s['Shipment']==shipment_id)
    key=api_key('GOOGLE_MAPS_API_KEY')
    if key:
        show_shipment_map(shipment,key)
        st.caption('Select any route card under the map to compare the available road paths and travel estimates.')
    else:
        st.warning('Set GOOGLE_MAPS_API_KEY in `.streamlit/secrets.toml` or the environment to load route alternatives.')
        st.code('[secrets]\nGOOGLE_MAPS_API_KEY = "your restricted browser key"')
        st.caption('Enable both Maps JavaScript API and Routes API, attach billing, and restrict the key to your local/app HTTP referrers.')
conn.close()
