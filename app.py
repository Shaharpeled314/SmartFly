
import streamlit as st
import openai
import requests
from datetime import datetime

# הגדרות API
openai.api_key = st.secrets["OPENAI_API_KEY"]
AMADEUS_CLIENT_ID = st.secrets["AMADEUS_CLIENT_ID"]
AMADEUS_CLIENT_SECRET = st.secrets["AMADEUS_CLIENT_SECRET"]
AMADEUS_API_BASE_URL = "https://api.amadeus.com"

@st.cache_data(ttl=1700)
def get_amadeus_access_token():
    url = f"{AMADEUS_API_BASE_URL}/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_CLIENT_ID,
        "client_secret": AMADEUS_CLIENT_SECRET
    }
    response = requests.post(url, data=data)
    return response.json()["access_token"]

def get_gpt_query(user_input):
    response = openai.ChatCompletion.create(
        model="ft:gpt-3.5-turbo-0125:personal::BNK4ZNHh",
        messages=[{
            "role": "user",
            "content": user_input
        }]
    )
    return response["choices"][0]["message"]["content"]

def post_process_query(gpt_output):
    try:
        parsed = eval(gpt_output)
        return {
            "originLocationCode": parsed.get("origin"),
            "destinationLocationCode": parsed.get("destination"),
            "departureDate": parsed.get("date"),
            "adults": parsed.get("adults", 1),
            "currencyCode": "USD",
            "max": 5
        }
    except Exception:
        return None

def search_flights(access_token, query):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "currencyCode": query["currencyCode"],
        "originDestinations": [{
            "id": "1",
            "originLocationCode": query["originLocationCode"],
            "destinationLocationCode": query["destinationLocationCode"],
            "departureDateTimeRange": {
                "date": query["departureDate"]
            }
        }],
        "travelers": [{
            "id": "1",
            "travelerType": "ADULT"
        }],
        "sources": ["GDS"],
        "searchCriteria": {
            "maxFlightOffers": query["max"]
        }
    }
    response = requests.post(f"{AMADEUS_API_BASE_URL}/v2/shopping/flight-offers", headers=headers, json=payload)
    return response.json()

st.set_page_config(page_title="Smart Flight Chat", page_icon="✈️", layout="wide")
st.title("🛫 מערכת חכמה לחיפוש טיסות")

if "chat" not in st.session_state:
    st.session_state.chat = []

user_input = st.chat_input("מה תרצה לדעת על טיסות?")

if user_input:
    st.session_state.chat.append(("user", user_input))
    gpt_output = get_gpt_query(user_input)
    st.session_state.chat.append(("assistant", "שאלתך עוברת עיבוד..."))

    query = post_process_query(gpt_output)
    if query:
        token = get_amadeus_access_token()
        results = search_flights(token, query)
        offers = results.get("data", [])

        if offers:
            answer = "מצאתי עבורך את הטיסות הבאות:
"
            for offer in offers:
                seg = offer["itineraries"][0]["segments"][0]
                dep = seg["departure"]["at"].split("T")[0]
                price = offer["price"]["grandTotal"]
                answer += f"- {seg['departure']['iataCode']} → {seg['arrival']['iataCode']} בתאריך {dep}, מחיר: {price} USD\n"
        else:
            answer = "לא נמצאו טיסות מתאימות לשאילתה שלך."
    else:
        answer = "לא הצלחתי להבין את השאילתה. נסה לנסח אותה אחרת."

    st.session_state.chat[-1] = ("assistant", answer)

for role, msg in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(msg)
