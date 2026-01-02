import streamlit as st
import pickle
import io
import requests
from PIL import Image
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------------- CONFIG ---------------- #
GOOGLE_DRIVE_FOLDER_ID = ["1d3hEvbix4blsM7An5Iztf0J2Eljok3AI","1iY-gPKT_diWgK7OP45Hg2SJzXcYrMLgV","1F7ooIYCJA1r0bhZm9XYNncA0iX5itmjr","1C0EBb08PKRs_4iSNEa_cmpJBkA7DNf-V"]
FACE_PKL_PATH = "face_directory.pkl"
LOOKUP_IMAGE_PATH = "faceLookup.jpg"
# THUMBNAIL_SIZE = (200, 200)
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
# ---------------------------------------- #

st.set_page_config(
    page_title="Face Sort Viewer",
    layout="wide"
)

st.title("📸 Face-Sorted Image Viewer")

# ---------- GOOGLE DRIVE AUTH ---------- #
@st.cache_resource
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

drive_service = get_drive_service()

# ---------- LOAD FACE DIRECTORY ---------- #
@st.cache_data
def load_face_directory():
    with open(FACE_PKL_PATH, "rb") as f:
        return pickle.load(f)

face_directory = load_face_directory()

# ---------- BUILD filename → fileId MAP ---------- #
@st.cache_data(show_spinner=True)
def build_filename_id_map():
    file_map = {}
    page_token = None

    for IDS in GOOGLE_DRIVE_FOLDER_ID:
            
        while True:
            response = drive_service.files().list(
                q=f"'{IDS}' in parents and trashed=false",
                fields="nextPageToken, files(id, name)",
                pageToken=page_token
            ).execute()

            for file in response.get("files", []):
                file_map[file["name"]] = file["id"]

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    return file_map

filename_to_id = build_filename_id_map()

# ---------- LOAD IMAGE FROM DRIVE ---------- #
@st.cache_data(show_spinner=False)
def load_image(file_id):
    url = f"https://drive.google.com/uc?id={file_id}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content)).convert("RGB")

# ---------- SIDEBAR ---------- #
st.sidebar.header("Navigation")

people = sorted(face_directory.keys())
DEFAULT_PERSON = "Fayiq" 

default_index = (
    people.index(DEFAULT_PERSON)
    if DEFAULT_PERSON in people
    else 0
)

selected_person = st.sidebar.selectbox(
    "Select Person",
    people,
    index=default_index
)

show_lookup = st.sidebar.button("Who am I? (Face Lookup)")

if show_lookup:
    with st.expander("🔍 Face Lookup Guide (Click to Expand)", expanded=True):
        st.image(
            LOOKUP_IMAGE_PATH,
            caption="Zoom in to match your face and find your person number",
            width='stretch'
        )
        
st.sidebar.info("To Zoom in, Right-click → Open image in new tab or Ctrl+Scroll (on desktop) / Pinch zoom (on mobile)")

# ---------- MAIN CONTENT ---------- #
st.subheader(f"👤 {selected_person}")

image_names = face_directory[selected_person]
st.caption(f"Images: {len(image_names)}")

columns = st.columns(4)

for idx, image_name in enumerate(image_names):
    with columns[idx % 4]:
        if image_name == "face_preview.jpg":
            continue
        file_id = filename_to_id.get(image_name)

        if not file_id:
            st.warning("Image not found in Drive")
            continue

        try:
            image = load_image(file_id)
            # image.thumbnail(THUMBNAIL_SIZE)
            st.image(image, caption=image_name,width='stretch')
        except Exception:
            st.error("Failed to load image")