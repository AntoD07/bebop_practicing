import streamlit as st

from scripts.major import root_ending

st.title("Music Practice App")
# Simple interaction
if st.button("Click me"):
    st.write("Welcome to your music practice session!")
