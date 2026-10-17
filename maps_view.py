"""Google Maps driving routes with user-selectable alternative roads."""
import json
from urllib.parse import quote

import streamlit.components.v1 as components


def show_shipment_map(shipment, api_key, height=620):
    origin = shipment.get('Origin') or shipment.get('origin')
    destination = shipment.get('Destination') or shipment.get('destination')
    route = {'origin': origin, 'destination': destination}
    route_json = json.dumps(route).replace('</', '<\\/')
    key_param = quote(api_key, safe='')
    html = f"""<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
html,body{{height:100%;margin:0;background:#0b1220;color:#e8eef7;font-family:Arial,sans-serif}}
#layout{{height:100%;display:flex;flex-direction:column}} #map{{flex:1;min-height:390px}}
#panel{{padding:12px 14px;background:#111c2f;border-top:1px solid #31435c}}
#status{{color:#b8c7dc;font-size:13px;margin-bottom:8px}} #routes{{display:flex;gap:8px;overflow-x:auto}}
.route{{min-width:170px;text-align:left;padding:9px 12px;border:1px solid #536781;border-radius:9px;background:#1a2940;color:#edf4ff;cursor:pointer}}
.route.active{{border-color:#2d8cff;background:#203d61}} .route small{{display:block;color:#b8c7dc;margin-top:4px}}
</style></head><body><div id="layout"><div id="map"></div><div id="panel"><div id="status">Connecting to Google Maps Routes…</div><div id="routes"></div></div></div>
<script>
const shipment = {route_json};
let map, routes = [], polylines = [], selected = 0;
function status(text){{document.getElementById('status').textContent=text;}}
function clearLines(){{for (const line of polylines) line.setMap(null); polylines=[];}}
function chooseRoute(index){{
  selected=index; clearLines();
  routes.forEach((route,i)=>{{
    const isSelected=i===selected;
    polylines.push(...route.createPolylines({{polylineOptions:{{map,strokeColor:isSelected?'#2D8CFF':'#91a9c7',strokeOpacity:isSelected?0.95:0.48,strokeWeight:isSelected?7:4}}}}));
  }});
  const bounds=routes[index].viewport; if(bounds) map.fitBounds(bounds,55);
  document.querySelectorAll('.route').forEach((el,i)=>el.classList.toggle('active',i===index));
}}
function renderRoutes(){{
 const list=document.getElementById('routes'); list.innerHTML='';
 routes.forEach((route,index)=>{{
   const button=document.createElement('button'); button.className='route';
   const label=route.routeLabels?.includes('DEFAULT_ROUTE')?'Recommended road route':`Alternative road route ${{index}}`;
   const km=(route.distanceMeters/1000).toFixed(1);
   const mins=Math.max(1,Math.round(route.durationMillis/60000));
   button.innerHTML=`${{label}}<small>${{km}} km · ${{mins}} min</small>`;
   button.onclick=()=>chooseRoute(index); list.appendChild(button);
 }});
 chooseRoute(0);
 status(`${{routes.length}} road route option(s) · Google driving route estimate; not live vehicle tracking.`);
}}
async function initMap(){{
 try{{
   const {{Map}}=await google.maps.importLibrary('maps');
   const {{Route}}=await google.maps.importLibrary('routes');
   map=new Map(document.getElementById('map'),{{center:{{lat:13.0827,lng:80.2707}},zoom:6,mapTypeControl:false,streetViewControl:false}});
   const result=await Route.computeRoutes({{origin:shipment.origin+', India',destination:shipment.destination+', India',travelMode:'DRIVING',routingPreference:'TRAFFIC_AWARE',computeAlternativeRoutes:true,fields:['path','routeLabels','viewport','distanceMeters','durationMillis']}});
   routes=result.routes||[];
   if(!routes.length){{status('Google returned no road route for these locations.');return;}}
   await routes[0].createWaypointAdvancedMarkers({{map}});
   renderRoutes();
 }}catch(error){{status('Google Routes error: '+(error?.message||'Check API access, billing, and enabled APIs.'));}}
}}
window.initMap=initMap;
</script>
<script async src="https://maps.googleapis.com/maps/api/js?key={key_param}&v=weekly&loading=async&callback=initMap"></script>
</body></html>"""
    components.html(html, height=height, scrolling=False)
