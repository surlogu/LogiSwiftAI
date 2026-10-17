import json
import streamlit as st
import pandas as pd
import plotly.express as px
from engine import SCENARIOS, connect, history, mistake_log, recover, sample_shipments, strategy_order
from agent.adk_agent import run_hybrid_agent

st.set_page_config(page_title='LogiSwift AI | Same-Day Parcel & Control Tower', page_icon='🚚', layout='wide')
st.markdown(
    '''<style>
    .stApp{background:#0b1220;color:#e5edf7}
    div[data-testid="stMetric"]{background:#172238;border:1px solid #293953;border-radius:14px;padding:15px}
    .block-container{padding-top:2rem}
    h1,h2,h3{color:#f3f8ff}
    </style>''',
    unsafe_allow_html=True
)

st.title('🚚 LogiSwift AI — Autonomous Logistics & Same-Day Parcel Handler')
st.caption('Detect → Diagnose → Act → Verify → Learn • Google ADK + Multimodal Control Tower')

conn = connect()
records = history(conn)
mistakes = mistake_log(conn)
shipments = sample_shipments()
recovered = sum(r['status'] == 'RECOVERED' for r in records)

c1, c2, c3, c4 = st.columns(4)
c1.metric('Shipments monitored', len(shipments))
c2.metric('Incidents processed', len(records))
c3.metric('Recovery rate', f'{recovered / len(records) * 100:.0f}%' if records else '—')
c4.metric('Avg agent runtime', f'{sum(r["latency_ms"] for r in records) / len(records):.2f} ms' if records else '—')

tab_lld, tab1, tab2, tab3 = st.tabs([
    '🩺 ORDER-101 Parcel Exception Handler (LLD Demo)',
    '🤖 Fleet Multi-Constraint Simulator',
    '📦 Fleet Shipments',
    '🧠 Learning & Audit'
])

with tab_lld:
    st.subheader('Same-Day Parcel Exception Handler — Chennai Live Demo')

    # 1. Quick Sample Preset Buttons (So nobody stares at a blank screen)
    st.markdown('**💡 Quick Sample Presets (Click to load):**')
    preset_c1, preset_c2, preset_c3 = st.columns(3)

    if preset_c1.button('📦 ORDER-101 (Medical / High Priority)'):
        st.session_state['preset_order'] = {
            "id": "ORDER-101", "pickup": "T. Nagar, Chennai", "drop": "Adyar, Chennai", "deadline": "18:00", "type": "medical_supplies"
        }
    if preset_c2.button('💻 ORDER-102 (Electronics / Normal)'):
        st.session_state['preset_order'] = {
            "id": "ORDER-102", "pickup": "Velachery, Chennai", "drop": "Anna Nagar, Chennai", "deadline": "20:00", "type": "electronics"
        }
    if preset_c3.button('🥛 ORDER-103 (Perishables / Express)'):
        st.session_state['preset_order'] = {
            "id": "ORDER-103", "pickup": "Koyambedu, Chennai", "drop": "Mylapore, Chennai", "deadline": "17:30", "type": "perishables"
        }

    # Load from state or use default ORDER-101
    default_p = st.session_state.get('preset_order', {
        "id": "ORDER-101", "pickup": "T. Nagar, Chennai", "drop": "Adyar, Chennai", "deadline": "18:00", "type": "medical_supplies"
    })

    # 2. Pre-populated form fields
    col_o1, col_o2, col_o3 = st.columns(3)
    with col_o1:
        order_id = st.text_input('Order ID', value=default_p["id"])
        pickup = st.text_input('Pickup Location', value=default_p["pickup"])
    with col_o2:
        drop = st.text_input('Drop Location', value=default_p["drop"])
        deadline = st.text_input('Deadline (24h)', value=default_p["deadline"])
    with col_o3:
        pkg_type = st.selectbox('Package Type', ['medical_supplies', 'electronics', 'perishables', 'documents'], index=['medical_supplies', 'electronics', 'perishables', 'documents'].index(default_p["type"]))
        fail_mode = st.selectbox(
            'Failure Simulator Mode',
            [
                '1 Failure: Courier A breakdown at 4:10 PM -> Reassign Courier B (Self-Healing)',
                '0 Failures: Happy Path (Courier A delivers directly)',
                '3 Failures: Consecutive breakdowns -> Escalate to Human Ops'
            ]
        )

    parcel_img = st.file_uploader('Optional: Upload Parcel Photo / Waybill (Multimodal Check)', type=['png', 'jpg', 'jpeg'])

    if st.button('🚀 Submit Order & Run Autonomous Handler', type='primary', use_container_width=True):
        sim_failures = 1 if fail_mode.startswith('1') else (0 if fail_mode.startswith('0') else 3)
        order_payload = {
            "order_id": order_id,
            "pickup": pickup,
            "drop": drop,
            "deadline": deadline,
            "package_type": pkg_type,
            "priority": "high"
        }
        img_bytes = parcel_img.read() if parcel_img else None
        mime = parcel_img.type if parcel_img else "image/jpeg"
        st.session_state['lld_output'] = run_hybrid_agent(
            order_payload,
            simulate_failures=sim_failures,
            image_bytes=img_bytes,
            mime_type=mime,
        )

    lld_out = st.session_state.get('lld_output')
    if lld_out:
        is_ok = lld_out['final_status'] == 'delivered'
        (st.success if is_ok else st.error)(
            f"FINAL STATUS: {lld_out['final_status'].upper()} | "
            f"Engine: {lld_out.get('engine', 'local')} | "
            f"Customer Notified: {lld_out['customer_notified']} | "
            f"Requires Human: {lld_out['requires_human']}"
        )
        col_trace, col_json = st.columns(2)
        with col_trace:
            st.markdown('#### Execution Trace (Detect → Diagnose → Act → Verify)')
            for s in lld_out['steps_trace']:
                st.markdown(f"**Step {s['step']} (`{s['state']}`): `{s['tool']}`** — {s['summary']}")
        with col_json:
            st.markdown('#### Final Agent JSON Contract')
            st.json({
                "order_id": lld_out["order_id"],
                "final_status": lld_out["final_status"],
                "attempts": lld_out["attempts"],
                "recovery_actions": lld_out["recovery_actions"],
                "a2a_handoffs": lld_out.get("a2a_handoffs", []),
                "customer_notified": lld_out["customer_notified"],
                "requires_human": lld_out["requires_human"]
            })
        st.markdown('#### Immutable Audit Trail (`data/audit_log.json`)')
        st.dataframe(pd.DataFrame(lld_out['audit_log']), use_container_width=True, hide_index=True)

with tab1:
    st.subheader('Simulate Fleet Scenarios & Multi-Constraint Self-Healing')
    a, b = st.columns(2)
    with a:
        scenario = st.selectbox('Failure scenario', list(SCENARIOS))
    with b:
        shipment = st.selectbox('Shipment ID', [s['Shipment'] for s in shipments])

    m1, m2 = st.columns(2)
    with m1:
        uploaded_file = st.file_uploader(
            'Optional: Upload Cargo / Dashcam Image',
            type=['png', 'jpg', 'jpeg', 'webp']
        )
    with m2:
        manifest_notes = st.text_input(
            'Optional: Driver Audio Transcript / Manifest Notes',
            placeholder='e.g., Fragile vaccine pallets...'
        )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button('⚡ Execute autonomous recovery', use_container_width=True):
            img_bytes = uploaded_file.read() if uploaded_file else None
            mime = uploaded_file.type if uploaded_file else 'image/jpeg'
            st.session_state['last_result'] = recover(
                shipment, scenario, conn, image_bytes=img_bytes, mime_type=mime, manifest_notes=manifest_notes
            )
            st.rerun()
    with col_btn2:
        if st.button('🔄 Run all six demo scenarios', use_container_width=True):
            for i, s in enumerate(SCENARIOS):
                recover(f'LS{1001 + i}', s, conn)
            st.rerun()

    result = st.session_state.get('last_result')
    if result:
        (st.success if result['status'] == 'RECOVERED' else st.warning)(
            f"{result['status']} | {result['attempts']} action(s) | {result['latency_ms']} ms | "
            f"Final ETA: {result['final_eta']}m | Weight: {result.get('final_weight_tons', 0)}t | Temp: {result.get('final_temp_c', 0)}°C"
        )
        for i, event in enumerate(result['timeline'], 1):
            icon = '✅' if event.get('verified') else '❌' if event.get('verified') is False else '🔍'
            st.markdown(f"**{icon} {i}. {event['stage']}** • {event.get('action', '')} {event['detail']}")

with tab2:
    df = pd.DataFrame(shipments)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.plotly_chart(
        px.histogram(df, x='Status', color='Priority', barmode='group', template='plotly_dark'),
        use_container_width=True
    )

with tab3:
    records = history(conn)
    if records:
        st.subheader('Learned Strategy Ranking (Self-Healing Policy)')
        ranking_rows = []
        for scen_name, cfg in SCENARIOS.items():
            failure_key = cfg['failure']
            ordered = [act for act, _ in strategy_order(failure_key, conn)]
            ranking_rows.append({
                'Scenario': scen_name,
                'Failure Code': failure_key,
                'Current Preferred Strategy': ordered[0],
                'Full Ranking Order': ' → '.join(ordered)
            })
        st.dataframe(pd.DataFrame(ranking_rows), use_container_width=True, hide_index=True)

        if mistakes:
            st.subheader('🛡️ Human-in-the-Loop (HITL): Audit & Override Learned Mistakes')
            st.caption(
                'By default, the agent applies penalties autonomously (AUTO_APPLIED). '
                'If a failure was a false positive (e.g., weather/sensor glitch), revoke it below to restore the strategy rank.'
            )
            st.dataframe(pd.DataFrame(mistakes), use_container_width=True, hide_index=True)

            col_m1, col_m2, col_m3, col_m4 = st.columns([1, 2, 2, 1])
            with col_m1:
                target_id = st.selectbox('Mistake ID', [m['id'] for m in mistakes])
            with col_m2:
                decision = st.selectbox(
                    'Auditor Decision',
                    ['REVOKED_FALSE_POSITIVE', 'APPROVED_BY_HUMAN', 'AUTO_APPLIED']
                )
            with col_m3:
                note = st.text_input('Audit Reason', value='External anomaly — pardon penalty')
            with col_m4:
                st.write('')
                st.write('')
                if st.button('Apply Audit', use_container_width=True):
                    from engine import audit_mistake_memory
                    audit_mistake_memory(target_id, decision, note, conn)
                    st.rerun()

        audit = pd.DataFrame([{k: v for k, v in r.items() if k != 'timeline'} for r in records])
        st.dataframe(audit, use_container_width=True, hide_index=True)
        selected = st.selectbox('Inspect audit trail', [r['id'] for r in records])
        st.json(json.loads(next(r['timeline'] for r in records if r['id'] == selected)))
        st.download_button(
            'Download audit CSV',
            audit.to_csv(index=False).encode(),
            file_name='logiswift_audit.csv',
            mime='text/csv'
        )
    else:
        st.info('Run an incident to populate the audit log.')

conn.close()