import json
import streamlit as st
import pandas as pd
import plotly.express as px
from engine import SCENARIOS, connect, history, recover, sample_shipments

st.set_page_config(page_title='LogiSwift AI | Autonomous Control Tower',page_icon='🚚',layout='wide')
st.markdown('''<style>.stApp{background:#0b1220;color:#e5edf7}div[data-testid="stMetric"]{background:#172238;border:1px solid #293953;border-radius:14px;padding:15px}.block-container{padding-top:2rem}h1,h2,h3{color:#f3f8ff}</style>''',unsafe_allow_html=True)
st.title('🚚 LogiSwift AI')
st.caption('Autonomous Logistics Control Tower • Observe → Reason → Act → Verify → Learn • Simulation demo')
conn=connect()
records=history(conn)
shipments=sample_shipments()
recovered=sum(r['status']=='RECOVERED' for r in records)
c1,c2,c3,c4=st.columns(4)
c1.metric('Shipments monitored',len(shipments))
c2.metric('Incidents processed',len(records))
c3.metric('Recovery rate',f'{recovered/len(records)*100:.0f}%' if records else '—')
c4.metric('Avg agent runtime',f'{sum(r["latency_ms"] for r in records)/len(records):.2f} ms' if records else '—')

tab1,tab2,tab3=st.tabs(['⚡ Autonomous Agent','📦 Shipments','📊 Feedback & Audit'])
with tab1:
    st.subheader('Simulate an incident and watch self-healing')
    a,b=st.columns(2)
    with a: scenario=st.selectbox('Failure scenario',list(SCENARIOS))
    with b: shipment=st.selectbox('Shipment ID',[s['Shipment'] for s in shipments])
    st.info('Actions are simulated. Recovery is accepted only when the verification rule passes. No live routes, drivers, or notifications are changed.')
    if st.button('🚀 Execute autonomous recovery',type='primary',use_container_width=True):
        result=recover(shipment,scenario,conn)
        st.session_state['last_result']=result
        st.rerun()
    if st.button('▶ Run all six demo scenarios',use_container_width=True):
        for i,s in enumerate(SCENARIOS): recover(f'LS{1001+i}',s,conn)
        st.rerun()
    result=st.session_state.get('last_result')
    if result:
        (st.success if result['status']=='RECOVERED' else st.warning)(f"{result['status']} | {result['attempts']} action(s) | {result['latency_ms']} ms")
        for i,event in enumerate(result['timeline'],1):
            icon='✅' if event.get('verified') else '🔄' if event.get('verified') is False else '🔹'
            st.markdown(f"**{icon} {i}. {event['stage']}** — {event.get('action','')} {event['detail']}")
with tab2:
    df=pd.DataFrame(shipments)
    st.dataframe(df,use_container_width=True,hide_index=True)
    chart=px.histogram(df,x='Status',color='Priority',barmode='group',title='Shipment status by priority',template='plotly_dark')
    st.plotly_chart(chart,use_container_width=True)
with tab3:
    records=history(conn)
    if records:
        audit=pd.DataFrame([{k:v for k,v in r.items() if k!='timeline'} for r in records])
        st.dataframe(audit,use_container_width=True,hide_index=True)
        st.subheader('Verified recovery feedback')
        outcomes=pd.DataFrame([{'Scenario':r['scenario'],'Outcome':r['status']} for r in records])
        st.plotly_chart(px.histogram(outcomes,x='Scenario',color='Outcome',barmode='group',template='plotly_dark'),use_container_width=True)
        selected=st.selectbox('Inspect audit trail', [r['id'] for r in records])
        st.json(json.loads(next(r['timeline'] for r in records if r['id']==selected)))
        st.download_button('Download audit CSV',audit.to_csv(index=False).encode(),file_name='logiswift_audit.csv',mime='text/csv')
    else: st.info('Run an incident to populate the audit log.')
conn.close()
