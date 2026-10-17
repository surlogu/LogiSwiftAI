"""Google Maps display for the project's synthetic shipment pairs."""

import json
from urllib.parse import quote

import streamlit.components.v1 as components


CITY_COORDINATES = {
    "Chennai": {"lat": 13.0827, "lng": 80.2707},
    "Bengaluru": {"lat": 12.9716, "lng": 77.5946},
    "Mumbai": {"lat": 19.0760, "lng": 72.8777},
    "Pune": {"lat": 18.5204, "lng": 73.8567},
    "Hyderabad": {"lat": 17.3850, "lng": 78.4867},
    "Vijayawada": {"lat": 16.5062, "lng": 80.6480},
    "Delhi": {"lat": 28.6139, "lng": 77.2090},
    "Jaipur": {"lat": 26.9124, "lng": 75.7873},
    "Coimbatore": {"lat": 11.0168, "lng": 76.9558},
    "Kochi": {"lat": 9.9312, "lng": 76.2673},
}


def show_shipment_map(shipment, api_key):
    origin = shipment["Origin"]
    destination = shipment["Destination"]
    route = {
        "origin": {"name": origin, **CITY_COORDINATES[origin]},
        "destination": {"name": destination, **CITY_COORDINATES[destination]},
    }
    route_json = json.dumps(route)
    key_param = quote(api_key, safe="")
    html = f"""<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>html,body,#map{{height:100%;margin:0}} #map{{min-height:520px}}</style>
  </head>
  <body>
    <div id="map"></div>
    <script>
      const route = {route_json};
      function initMap() {{
        const map = new google.maps.Map(document.getElementById('map'), {{
          center: route.origin,
          zoom: 6,
          mapTypeControl: false,
          streetViewControl: false
        }});
        const bounds = new google.maps.LatLngBounds();
        [route.origin, route.destination].forEach((point, index) => {{
          const position = {{lat: point.lat, lng: point.lng}};
          bounds.extend(position);
          new google.maps.Marker({{
            map,
            position,
            title: (index === 0 ? 'Origin: ' : 'Destination: ') + point.name,
            label: index === 0 ? 'A' : 'B'
          }});
        }});
        new google.maps.Polyline({{
          map,
          path: [route.origin, route.destination],
          geodesic: true,
          strokeColor: '#2D8CFF',
          strokeOpacity: 0.9,
          strokeWeight: 4
        }});
        map.fitBounds(bounds, 70);
      }}
      window.initMap = initMap;
    </script>
    <script async src="https://maps.googleapis.com/maps/api/js?key={key_param}&loading=async&callback=initMap"></script>
  </body>
</html>"""
    components.html(html, height=540, scrolling=False)
