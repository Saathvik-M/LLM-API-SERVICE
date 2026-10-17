import requests
import streamlit as st
 
from google import genai
 
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime
)
 
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

 
# STREAMLIT CONFIG
st.set_page_config(
    page_title="Weather LLM Assistant",
    page_icon="🌤️",
    layout="wide"
)
 
st.title("🌤️ Weather LLM Assistant")
 
 
# DATABASE

DATABASE_URL = "sqlite:///./weather_service.db"
 
 
@st.cache_resource
def get_engine():
    # cache_resource ensures the engine (and its connection pool)
    # is created once per app process, not once per rerun/click.
    return create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
 
 
engine = get_engine()
 
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
 
Base = declarative_base()
 
 
class WeatherLog(Base):
    __tablename__ = "weather_logs"
 
    id = Column(Integer, primary_key=True, index=True)
 
    location = Column(
        String(100),
        nullable=False
    )
 
    user_query = Column(
        Text,
        nullable=False
    )
 
    weather_data = Column(
        Text,
        nullable=False
    )
 
    llm_response = Column(
        Text,
        nullable=False
    )
 
    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
 
 
Base.metadata.create_all(bind=engine)
 
# GEMINI API KEY 
 
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = ""
 
with st.sidebar:
 
    st.header("🔑 Gemini API")
 
    st.session_state.gemini_api_key = st.text_input(
        "Enter your Gemini API Key",
        value=st.session_state.gemini_api_key,
        type="password",
        help=(
            "Get a free key at https://aistudio.google.com/apikey. "
            "It's kept only in this browser session — never written "
            "to disk or the database."
        )
    )
 
    gemini_api_key = st.session_state.gemini_api_key
 
    if gemini_api_key:
        st.success("API key ready")
    else:
        st.warning(
            "Enter your Gemini API key to use the AI assistant."
        )
 
    st.divider()
 
    st.caption(
        "Your API key is never stored in the application database "
        "or logged — it only lives in this browser session and is "
        "sent directly to Google's API."
    )
# WEATHER FUNCTION
def get_coordinates_and_weather(city_name):
 
    geo_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
        f"?name={city_name}"
        "&count=1"
        "&language=en"
        "&format=json"
    )
 
    geo_response = requests.get(
        geo_url,
        timeout=10
    )
 
    geo_response.raise_for_status()
 
    geo_data = geo_response.json()
 
    if not geo_data.get("results"):
        raise ValueError(
            "Location not found."
        )
 
    location = geo_data["results"][0]
 
    lat = location["latitude"]
    lon = location["longitude"]
 
    resolved_name = location["name"]
 
    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lon}"
        "&current="
        "temperature_2m,"
        "relative_humidity_2m,"
        "wind_speed_10m,"
        "precipitation"
    )
 
    weather_response = requests.get(
        weather_url,
        timeout=10
    )
 
    weather_response.raise_for_status()
 
    weather_data = weather_response.json()
 
    return {
        "city": resolved_name,
        "country": location.get("country", ""),
        "current": weather_data.get(
            "current",
            {}
        )
    }

# GEMINI FUNCTION
def generate_weather_response(
    api_key,
    weather_info,
    user_query
):
 
    try:
        client = genai.Client(
            api_key=api_key
        )
 
        prompt = f"""
You are a helpful weather assistant.
 
Answer the user's question using the live weather
information provided below.
 
Location:
{weather_info['city']}, {weather_info['country']}
 
Current Weather:
{weather_info['current']}
 
User Question:
{user_query}
 
Give a clear, useful and practical answer.
"""
 
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
 
        return response.text
 
    except Exception as e:
        # Surface a clearer message for the most common failure:
        # an invalid/expired key, instead of a raw SDK traceback.
        msg = str(e).lower()
        if "api key" in msg or "permission" in msg or "401" in msg or "403" in msg:
            raise ValueError(
                "Your Gemini API key was rejected. Double-check it "
                "in the sidebar (get one at "
                "https://aistudio.google.com/apikey)."
            )
        raise
    
# TABS
tab1, tab2 = st.tabs(
    [
        "🌤️ Ask Weather",
        "📚 Manage Logs"
    ]
)

# TAB 1 - ASK WEATHER
with tab1:
 
    col1, col2 = st.columns(
        [1, 2]
    )
 
    with col1:
 
        city = st.text_input(
            "City Name",
            "Tokyo"
        )
 
        query = st.text_area(
            "Your Question",
            "What should I wear outside right now?"
        )
 
        ask_btn = st.button(
            "Submit Query",
            type="primary"
        )
 
 
    with col2:
 
        if ask_btn:
 
            if not gemini_api_key:
 
                st.error(
                    "Please enter your Gemini API key "
                    "in the sidebar."
                )
 
                st.stop()
 
            if not city.strip():
 
                st.error(
                    "Please enter a city."
                )
 
                st.stop()
 
            if not query.strip():
 
                st.error(
                    "Please enter a question."
                )
 
                st.stop()
 
 
            with st.spinner(
                "Fetching weather and generating response..."
            ):
 
                try:
 
                    # Get weather
                    weather_info = (
                        get_coordinates_and_weather(
                            city
                        )
                    )
 
 
                    # Generate AI response
                    answer = generate_weather_response(
                        gemini_api_key,
                        weather_info,
                        query
                    )
 
 
                    # Save to database
                    db = SessionLocal()
 
                    log = WeatherLog(
                        location=(
                            f"{weather_info['city']}, "
                            f"{weather_info['country']}"
                        ),
                        user_query=query,
                        weather_data=str(
                            weather_info["current"]
                        ),
                        llm_response=answer
                    )
 
                    db.add(log)
                    db.commit()
                    db.refresh(log)
 
                    db.close()
 
 
                    # Display result
                    st.subheader(
                        f"📍 {weather_info['city']}, "
                        f"{weather_info['country']}"
                    )
 
                    st.write(answer)
 
                    with st.expander(
                        "🌦️ Raw Weather Data"
                    ):
 
                        st.json(
                            weather_info
                        )
 
 
                except Exception as e:
 
                    st.error(
                        f"Something went wrong: {str(e)}"
                    )
 
# TAB 2 - DATABASE LOGS
with tab2:
 
    st.subheader(
        "📚 Weather Query History"
    )
 
    if st.button(
        "🔄 Refresh History"
    ):
 
        st.rerun()
 
 
    db = SessionLocal()
 
    logs = (
        db.query(WeatherLog)
        .order_by(
            WeatherLog.id.desc()
        )
        .all()
    )
 
 
    if not logs:
 
        st.info(
            "No weather queries have been saved yet."
        )
 
 
    for log in logs:
 
        with st.expander(
            f"Log #{log.id} - "
            f"{log.location}"
        ):
 
            st.write(
                f"**Query:** {log.user_query}"
            )
 
            st.write(
                f"**Answer:** {log.llm_response}"
            )
 
            st.caption(
                f"**Weather Snapshot:** "
                f"{log.weather_data}"
            )
 
            st.caption(
                f"Created: {log.created_at}"
            )
 
 
            col1, col2 = st.columns(2)
 
 
            # UPDATE
            with col1:
 
                new_query = st.text_input(
                    "Edit query",
                    value=log.user_query,
                    key=f"edit_{log.id}"
                )
 
                if st.button(
                    "Update Query",
                    key=f"update_{log.id}"
                ):
 
                    log.user_query = new_query
 
                    db.commit()
 
                    st.success(
                        "Query updated!"
                    )
 
                    st.rerun()
 
 
            # DELETE
            with col2:
 
                if st.button(
                    "🗑️ Delete Log",
                    key=f"delete_{log.id}"
                ):
 
                    db.delete(log)
 
                    db.commit()
 
                    st.success(
                        "Log deleted!"
                    )
 
                    st.rerun()
 
 
    db.close()
 
