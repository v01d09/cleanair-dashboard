import functions_framework
from google.cloud import firestore
from google import genai
from google.genai import types
import json
import requests
import os
from pydantic import BaseModel, Field
from typing import Literal

# Initialize global SDK handlers
db = firestore.Client(project="void-501114", database="clean")
import threading
client_lock = threading.Lock()
gemini_client = None

def get_gemini_client():
    global gemini_client
    with client_lock:
        if gemini_client is None:
            # Fetches API key from environment variable (with dummy placeholder fallback for security)
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "YOUR_GEMINI_API_KEY_HERE"
            print(f"System: Initializing Gemini client. API key resolved.")
            gemini_client = genai.Client(api_key=api_key)
    return gemini_client

def generate_content_safe(contents, system_instruction=None, response_schema=None):
    client = get_gemini_client()
    models = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    last_err = None
    for model in models:
        try:
            config_params = {}
            if system_instruction:
                config_params["system_instruction"] = system_instruction
            if response_schema:
                config_params["response_schema"] = response_schema
                config_params["response_mime_type"] = "application/json"
            
            config = types.GenerateContentConfig(**config_params)
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            return response
        except Exception as e:
            last_err = e
            print(f"System: Model {model} request failed: {e}. Attempting fallback...")
    raise last_err

class PollutionIncidentTicket(BaseModel):
    is_pollution_incident: bool = Field(description="Set to false if the image is a stock photo, internet download, screenshot, non-pollution scene, or spam. Otherwise true.")
    hazard_type: str = Field(description="Specific categorization of the environmental hazard.")
    severity_level: Literal["LOW", "MEDIUM", "CRITICAL"] = Field(description="LOW: localized patch. MEDIUM: blocks junctions or neighborhoods. CRITICAL: macro regional fire/industrial plume.")
    calculated_local_aqi: int = Field(description="Calibrated scale between 0 and 500. If live telemetry is missing, estimate strictly from visual fuel and density indicators.")
    environmental_analysis: str = Field(description="Detailed forensic summary of the source fuel, wind dispersion vectors, and health impact analysis.")
    predictive_24h_spike_warning: str = Field(description="Meteorological projection of where the smoke plume or dust cloud will migrate over the next 24 hours.")
    actionable_instruction_for_crew: str = Field(description="Explicit operational commands for municipal environmental dispatch teams to mitigate the hazard.")

# =====================================================================
# CALIBRATED MULTI-AGENT INTELLIGENCE MESH
# =====================================================================
def run_visual_agent(image_url):
    print("Agent 1: Running street-level visual analysis...")
    try:
        if "twilio.com" in image_url:
            TWILIO_SID = os.environ.get("TWILIO_SID") or "YOUR_TWILIO_SID_HERE"
            TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN") or "YOUR_TWILIO_AUTH_TOKEN_HERE"
            response_media = requests.get(image_url, auth=(TWILIO_SID, TWILIO_AUTH_TOKEN), timeout=10)
        else:
            response_media = requests.get(image_url, timeout=10)
            
        if response_media.status_code != 200:
            raise Exception(f"Media download returned status code: {response_media.status_code}")
        image_bytes = response_media.content
    except Exception as e:
        print(f"Vision Agent Network Error: {e}")
        return "VISUAL EVIDENCE REPORT: Asset offline. Default to coordinates fallback mode."
        
    system_instruction = """
    You are an Air Quality Inspector. Check if this street photo is an authentic, real-time phone snap of a pollution hazard, or a stock photo, screenshot, or internet download.
    Write a brief forensic report (under 50 words). 
    CRITICAL: State if it is AUTHENTIC or SPAM. Note fuel source and severity (low impact if just a small trash/biomass pile, e.g. +30 AQI).
    """
    
    response = generate_content_safe(
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
            "Execute complete forensic evaluation of this environmental incident scene."
        ],
        system_instruction=system_instruction
    )
    return f"VISUAL EVIDENCE REPORT:\n{response.text}"

def run_data_agent(latitude, longitude):
    print("Agent 2: Retrieving live environmental telemetry...")
    maps_key = os.environ.get("GOOGLE_MAPS_API_KEY") or "YOUR_GOOGLE_MAPS_API_KEY_HERE"
    datagov_key = os.environ.get("DATAGOV_API_KEY") or "YOUR_DATAGOV_API_KEY_HERE"
    gmaps_aqi = "UNKNOWN"
    weather_data = "UNKNOWN"
    gov_aqi_records = "OFFLINE"

    try:
        gmaps_url = f"https://airquality.googleapis.com/v1/currentConditions:lookup?key={maps_key}"
        payload = {"location": {"latitude": latitude, "longitude": longitude}, "extraComputations": ["METEOROLOGICAL_DATA"]}
        gmaps_res = requests.post(gmaps_url, json=payload, timeout=5).json()
        indexes = gmaps_res.get("indexes", [])
        if indexes: gmaps_aqi = str(indexes[0].get("aqi"))
        meteorology = gmaps_res.get("meteorologicalData", {})
        if meteorology:
            weather_data = f"Wind Speed: {meteorology.get('windSpeed', {}).get('value')} m/s, Humidity: {meteorology.get('relativeHumidity')}%"
    except Exception as e: 
        pass

    try:
        resource_id = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
        gov_url = f"https://api.data.gov.in/resource/{resource_id}?api-key={datagov_key}&format=json&limit=1"
        gov_res = requests.get(gov_url, timeout=4).json()
        gov_aqi_records = str(gov_res.get('records', []))
    except Exception as e: 
        pass

    compiled_telemetry = f"Live Ambient Google AQI: {gmaps_aqi}. Meteorological Grid: {weather_data}. Nearest Station Records: {gov_aqi_records}"
    
    response = generate_content_safe(
        contents=f"Synthesize this baseline atmospheric payload: {compiled_telemetry}",
        system_instruction="You are an Atmospheric Scientist. Summarize ambient telemetry parameters cleanly. Be extremely concise (under 50 words)."
    )
    return f"REGIONAL DATA OVERHEAD REPORT:\n{response.text}\n[RAW METRICS: GoogleAQI={gmaps_aqi}]"

def run_maps_agent(latitude, longitude):
    print("Agent 3: Resolving spatial and location context...")
    maps_key = os.environ.get("GOOGLE_MAPS_API_KEY") or "YOUR_GOOGLE_MAPS_API_KEY_HERE"
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={maps_key}"
    try:
        res = requests.get(url, timeout=5).json()
        maps_context = res["results"][0]["formatted_address"] if res.get("results") else "Remote/Unmapped Zone"
    except Exception as e: 
        maps_context = "Spatial geocoding layer offline."
        
    response = generate_content_safe(
        contents=f"Evaluate urban exposure for this location string: {maps_context}",
        system_instruction="You are a GIS Spatial Analyst. Assess location exposure. Be extremely concise (under 50 words)."
    )
    return f"GOOGLE MAPS SPATIAL LANDMARK CONTEXT:\n{response.text}"

def run_predictive_agent(report_v, report_d):
    print("Agent 4: Projecting meteorological dispersion trajectory...")
    response = generate_content_safe(
        contents=f"Execute mathematical dispersion plume projection using: {report_v} and {report_d}",
        system_instruction="You are a Plume Dispersion Physicist. Project trajectory over 24 hours. Be extremely concise (under 50 words)."
    )
    return f"24-HOUR METEOROLOGICAL DISPERSION SPIKE REPORT:\n{response.text}"

# =====================================================================
# UNIFIED CONVERGENT MASTER INTAKE PIPELINE
# =====================================================================
@functions_framework.http
def handle_unified_intake(request):
    # CORS Handshake preflight routing
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    response_headers = {'Access-Control-Allow-Origin': '*'}

    # Check for custom action routes
    action = None
    request_json = {}
    if request.method == 'GET':
        action = request.args.get('action')
    elif request.method == 'POST':
        try:
            request_json = request.get_json(silent=True) or {}
            action = request_json.get('action')
        except Exception:
            pass

    if action == 'proxy_image':
        url = request.args.get('url') if request.method == 'GET' else request_json.get('url')
        if not url:
            return ("Missing url parameter", 400, response_headers)
        try:
            TWILIO_SID = os.environ.get("TWILIO_SID") or "YOUR_TWILIO_SID_HERE"
            TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN") or "YOUR_TWILIO_AUTH_TOKEN_HERE"
            res = requests.get(url, auth=(TWILIO_SID, TWILIO_AUTH_TOKEN), timeout=15)
            headers = {**response_headers, 'Content-Type': res.headers.get('Content-Type', 'image/jpeg')}
            return (res.content, res.status_code, headers)
        except Exception as e:
            return (f"Image proxy error: {str(e)}", 500, response_headers)

    if action == 'analyze_sector':
        prompt = request_json.get('prompt')
        if not prompt:
            return (json.dumps({"error": "Missing prompt parameter"}), 400, {**response_headers, 'Content-Type': 'application/json'})
        try:
            response = generate_content_safe(
                contents=prompt,
                system_instruction="You are the Clean Air Command Intel Unit. Provide ultra-concise, high-impact tactical briefings for municipal dispatch supervisors. Use bullet points."
            )
            return (json.dumps({"response": response.text}), 200, {**response_headers, 'Content-Type': 'application/json'})
        except Exception as e:
            return (json.dumps({"error": str(e)}), 500, {**response_headers, 'Content-Type': 'application/json'})

    latitude, longitude, media_url, doc_id = None, None, None, None
    hazard_notes = "Portal Ingestion Entry Track"
    is_whatsapp_request = False

    # --- ROUTE A: Handle Incoming WhatsApp Form Submissions ---
    if request.form:
        is_whatsapp_request = True
        sender = request.form.get('From', '')
        latitude = request.form.get('Latitude')
        longitude = request.form.get('Longitude')
        num_media = int(request.form.get('NumMedia', 0))
        media_url = request.form.get('MediaUrl0') if num_media > 0 else None
        
        doc_id = sender.replace("whatsapp:", "").replace("+", "USER_")
        hazard_notes = "Incoming raw dispatch payload via WhatsApp mobile link"

    # --- ROUTE B: Handle Incoming Direct Website JSON Requests ---
    else:
        try:
            # We already read request_json above if it was a JSON POST request
            latitude = request_json.get("latitude")
            longitude = request_json.get("longitude")
            media_url = request_json.get("media_url")
            hazard_notes = request_json.get("hazard_notes") or hazard_notes
            doc_id = request_json.get("document_id")
        except Exception as json_err:
            print(f"❌ JSON Parse Exception: {json_err}")

    # CRITICAL SECURITY GUARDRAIL: Terminate early if the payload is empty or corrupt
    if not doc_id or (latitude is None and longitude is None and media_url is None):
        print("Guardrail: Suppressed incomplete network request.")
        return ("Ignored incomplete entry", 200, response_headers)

    # State Cache Sync Layer
    doc_ref = db.collection('whatsapp_holding_bay').document(doc_id)
    doc_snapshot = doc_ref.get()
    cached_data = doc_snapshot.to_dict() if doc_snapshot.exists else {}

    if latitude: cached_data['latitude'] = float(latitude)
    if longitude: cached_data['longitude'] = float(longitude)
    if media_url: cached_data['media_url'] = media_url
    if hazard_notes: cached_data['hazard_notes'] = hazard_notes
    cached_data['timestamp'] = firestore.SERVER_TIMESTAMP

    # Write state snapshot back to collection
    doc_ref.set(cached_data)

    final_lat = cached_data.get('latitude')
    final_lng = cached_data.get('longitude')
    final_url = cached_data.get('media_url')
    final_notes = cached_data.get('hazard_notes', hazard_notes)

    # --- Full Execution Verification ---
    if final_lat and final_lng and final_url:
        # Prevent concurrent double-execution from webhook retries
        if cached_data.get('processing') is True:
            print(f"System: Pipeline already running for {doc_id}. Suppressing duplicate trigger.")
            if is_whatsapp_request:
                twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Thanks for your contribution, your request will be updated shortly.</Message>
</Response>"""
                headers = {**response_headers, 'Content-Type': 'application/xml'}
                return (twiml, 200, headers)
            return ("Duplicate request suppressed", 200, response_headers)

        # Set processing lock flag
        cached_data['processing'] = True
        doc_ref.set(cached_data)

        print(f"System: Starting analysis pipeline for session: {doc_id}...")
        try:
            # Initialize Gemini client on main thread to avoid thread race conditions
            get_gemini_client()
            
            from concurrent.futures import ThreadPoolExecutor
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_v = executor.submit(run_visual_agent, final_url)
                future_d = executor.submit(run_data_agent, final_lat, final_lng)
                future_m = executor.submit(run_maps_agent, final_lat, final_lng)
                
                report_v = future_v.result()
                report_d = future_d.result()
                report_m = future_m.result()
                
            report_p = run_predictive_agent(report_v, report_d)
            
            print("Supervisor Agent: Synthesizing reports into final ticket...")
            compiled_brief = "\n---\n".join([report_v, report_d, report_m, report_p, f"USER NOTES: {final_notes}"])
            
            supervisor_instruction = """
            You are the Central Director of the response grid. Synthesize sub-agent reports into a structured ticket matching the Pydantic schema perfectly.
            
            CRITICAL COMPACTNESS CONSTRAINT:
            - Make sure 'environmental_analysis', 'predictive_24h_spike_warning', and 'actionable_instruction_for_crew' are under 50 words each. Do NOT write paragraphs.
            
            AUTHENTICITY FILTER:
            - If the Visual Report indicates the image is SPAM, a stock photo, or fake, set 'is_pollution_incident' to False.
            
            CALIBRATED AQI MATRIX (Use GoogleAQI baseline if available):
            - Minor low-priority fires/isolated small trash/leaf/plastic piles: Severity LOW, AQI between 115 and 140 (only increase baseline by +30 or +40).
            - Medium dense plume blocking junctions/street smog: Severity MEDIUM, AQI between 180 and 240.
            - Industrial fires/massive macro columns: Severity CRITICAL, AQI between 350 and 500.
            """
            
            response_supervisor = generate_content_safe(
                contents=f"Synthesize this operational intelligence briefing array:\n{compiled_brief}",
                system_instruction=supervisor_instruction,
                response_schema=PollutionIncidentTicket
            )
            
            master_ticket = json.loads(response_supervisor.text)
            master_ticket['latitude'] = final_lat
            master_ticket['longitude'] = final_lng
            master_ticket['timestamp'] = firestore.SERVER_TIMESTAMP
            master_ticket['citizen_image'] = final_url
            
            # Dynamic DB routing based on AI validation
            is_valid = master_ticket.get('is_pollution_incident', True)
            if is_valid:
                master_ticket['status'] = "PENDING"
                db.collection('verified_incidents').add(master_ticket)
                print("System: Valid ticket routed to verified_incidents.")
            else:
                master_ticket['status'] = "UNVERIFIED"
                db.collection('not_verified').add(master_ticket)
                print("System: Unverified/spam report routed to not_verified.")
            
            # Flush queue index tracking tokens
            doc_ref.delete()
            print(f"Queue: Cleared tracking index for {doc_id}.")
            
        except Exception as e:
            print(f"Error: Core processing mesh runtime failure: {str(e)}")
            if is_whatsapp_request:
                twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Thanks for your contribution, your request will be updated shortly.</Message>
</Response>"""
                headers = {**response_headers, 'Content-Type': 'application/xml'}
                return (twiml, 200, headers)
            return (f"AI Engine Exception: {str(e)}", 500, response_headers)
    else:
        print(f"📥 [State Synced]: Telemetry packet buffered. Awaiting next input track for session: {doc_id}")
        if is_whatsapp_request:
            twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Thanks for your contribution, your request will be updated shortly.</Message>
</Response>"""
            headers = {**response_headers, 'Content-Type': 'application/xml'}
            return (twiml, 200, headers)
        return ("State Cached Safely", 200, response_headers)

    if is_whatsapp_request:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Thanks for your contribution, your request will be updated shortly.</Message>
</Response>"""
        headers = {**response_headers, 'Content-Type': 'application/xml'}
        return (twiml, 200, headers)

    return ("OK", 200, response_headers)
