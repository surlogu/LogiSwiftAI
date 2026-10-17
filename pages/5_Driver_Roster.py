import pandas as pd
import streamlit as st

from engine import connect, driver_records, reset_workspace, shipment_workflows
from ui_common import configure_page


configure_page('Driver Roster | LogiSwift AI', '🧑‍✈️')
st.title('🧑‍✈️ Driver Roster')
st.caption('View driver availability and current assignments. Assigned drivers are excluded from replacement suggestions.')
conn = connect()

st.subheader('Reset workspace')
st.write('This permanently clears all saved shipments, route/recovery choices, likes, and audit history from SQLite, then marks every driver available so you can assign them again.')
if st.button('Clear all shipments, routes, and driver assignments', type='primary', use_container_width=True):
    reset_count = reset_workspace(conn)
    if reset_count:
        st.success(f'Cleared {reset_count} shipment(s), route and audit records. All drivers are available for reassignment.')
    else:
        st.success('The shipment database is already clear. All drivers are available for reassignment.')

workflows = shipment_workflows(conn)
active_lifecycles = {'DRIVER_ASSIGNED', 'DRIVER_REASSIGNED', 'RECOVERY_APPROVED', 'IN_TRANSIT', 'AWAITING_APPROVAL', 'ISSUE_REPORTED', 'ESCALATED_TO_HUMAN'}
active_by_driver = {}
for shipment in workflows:
    if shipment['Driver ID'] and shipment['Lifecycle'] in active_lifecycles:
        active_by_driver.setdefault(shipment['Driver ID'], []).append(
            f"{shipment['Shipment']} · {shipment['Origin']} → {shipment['Destination']} · {shipment['Lifecycle']}"
        )

drivers = driver_records(conn)
for driver in drivers:
    assignments = active_by_driver.get(driver['driver_id'], [])
    driver['Availability'] = 'Available' if driver['available'] and not assignments else 'Assigned'
    driver['Active shipment'] = '; '.join(assignments) if assignments else '—'
    driver['Reliability'] = f"{driver.pop('reliability'):.0%}"
    driver.pop('available')
    driver.pop('eta_minutes')
    driver.pop('current_location')

st.subheader('Driver availability')
if drivers:
    st.dataframe(pd.DataFrame(drivers), use_container_width=True, hide_index=True)
else:
    st.info('No drivers are configured.')

conn.close()
