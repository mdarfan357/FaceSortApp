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
# THUMBNAIL_SIZE = (240, 240)
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
IMAGES_PER_PAGE = 16   # 🔴 CRITICAL FOR MEMORY
# ---------------------------------------- #

st.set_page_config(page_title="Face Sort Viewer", layout="wide")
st.title("📸 Face-Sorted Image Viewer")

# ---------- GOOGLE DRIVE AUTH ---------- #
@st.cache_resource
def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

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
    mapping = {}
    page_token = None

    for IDS in GOOGLE_DRIVE_FOLDER_ID:
            
        while True:
            response = drive_service.files().list(
                q=f"'{IDS}' in parents and trashed=false",
                fields="nextPageToken, files(id, name)",
                pageToken=page_token
            ).execute()

            for file in response.get("files", []):
                mapping[file["name"]] = file["id"]

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    return mapping

filename_to_id = build_filename_id_map()

# ---------- LOAD IMAGE (THUMBNAIL ONLY) ---------- #
@st.cache_data(show_spinner=False, max_entries=100)
def load_image_thumbnail(file_id):
    url = f"https://drive.google.com/uc?id={file_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()

    img = Image.open(io.BytesIO(r.content))
    # img.draft("RGB", THUMBNAIL_SIZE)   # 🔴 avoids full decode
    # img.thumbnail(THUMBNAIL_SIZE)
    return img.convert("RGB")

# ---------- SIDEBAR (ONLY 2 ELEMENTS) ---------- #
st.sidebar.header("Navigation")


people = sorted(face_directory.keys())
DEFAULT_PERSON = "Nimra" 

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
st.sidebar.info("To Zoom in, Right-click → Open image in new tab or Ctrl+Scroll (on desktop) / Pinch zoom (on mobile)")

# ---------- LOOKUP IMAGE (ZOOMABLE) ---------- #
if show_lookup:
    with st.expander("🔍 Face Lookup Guide (Click to Expand)", expanded=True):
        st.image(
            LOOKUP_IMAGE_PATH,
            caption="Zoom in to match your face and find your person number",
            width='stretch'
        )

# ---------- PAGINATION LOGIC ---------- #
image_names = face_directory[selected_person]
total_images = len(image_names)
total_pages = (total_images - 1) // IMAGES_PER_PAGE + 1

st.subheader(f"👤 {selected_person}")
st.caption(f"Images: {total_images} • Pages: {total_pages}")

page = st.number_input(
    "Page",
    min_value=1,
    max_value=total_pages,
    value=1,
    step=1
)

start = (page - 1) * IMAGES_PER_PAGE
end = start + IMAGES_PER_PAGE
visible_images = image_names[start:end]

st.caption(
    "Images are loaded in pages to reduce memory usage. "
    "Use the page selector to browse."
)

# ---------- IMAGE GRID ---------- #
cols = st.columns(4)

for idx, image_name in enumerate(visible_images):
    with cols[idx % 4]:
        file_id = filename_to_id.get(image_name)

        if not file_id:
            st.warning("Missing file")
            continue

        try:
            img = load_image_thumbnail(file_id)
            st.image(img, caption=image_name,width='stretch')
            img.close()  # 🔴 IMPORTANT: free memory
        except Exception:
            st.error("Failed to load image")
