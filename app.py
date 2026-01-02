import streamlit as st
import pickle
import io
import os
import requests
from PIL import Image
from google.oauth2 import service_account
from googleapiclient.discovery import build
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= CONFIG ================= #
GOOGLE_DRIVE_FOLDER_ID = ["1d3hEvbix4blsM7An5Iztf0J2Eljok3AI","1iY-gPKT_diWgK7OP45Hg2SJzXcYrMLgV","1F7ooIYCJA1r0bhZm9XYNncA0iX5itmjr","1C0EBb08PKRs_4iSNEa_cmpJBkA7DNf-V"]
FACE_PKL_PATH = "face_directory.pkl"
LOOKUP_IMAGE_PATH = "faceLookup.jpg"

PREVIEW_SIZE = (320, 320)
IMAGES_PER_PAGE = 24
MAX_WORKERS = 6
CACHE_DIR = ".preview_cache"

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
# ========================================= #

os.makedirs(CACHE_DIR, exist_ok=True)

st.set_page_config(
    page_title="Face Sorted Viewer",
    layout="wide"
)

st.title("📸 Face-Sorted Image Viewer")

# ================= GOOGLE DRIVE ================= #
@st.cache_resource
def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

drive_service = get_drive_service()

# ================= LOAD FACE DIRECTORY ================= #
@st.cache_data
def load_face_directory():
    with open(FACE_PKL_PATH, "rb") as f:
        return pickle.load(f)

face_directory = load_face_directory()

# ================= FILE NAME → FILE ID MAP ================= #
@st.cache_data(show_spinner=True)
def build_filename_to_id():
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

filename_to_id = build_filename_to_id()

# ================= PREVIEW IMAGE LOADER ================= #
def load_preview(file_id):
    cache_path = os.path.join(CACHE_DIR, f"{file_id}.png")

    if os.path.exists(cache_path):
        return Image.open(cache_path)

    url = f"https://drive.google.com/uc?id={file_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()

    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    img.thumbnail(PREVIEW_SIZE)  # preview ONLY
    img.save(cache_path, format="PNG")

    return Image.open(cache_path)

# ================= SIDEBAR ================= #
st.sidebar.header("Navigation")

people = sorted(face_directory.keys())
default_person = max(face_directory, key=lambda k: len(face_directory[k]))

selected_person = st.sidebar.selectbox(
    "Select Person",
    people,
    index=people.index(default_person)
)

show_lookup = st.sidebar.button("Who am I? (Face Lookup)")

if show_lookup:
    with st.expander("🔍 Face Lookup Guide", expanded=True):
        st.image(
            LOOKUP_IMAGE_PATH,
            width='stretch',
            caption="Zoom in to identify your person number"
        )

# ================= PAGINATION ================= #
image_names = face_directory[selected_person]
total_images = len(image_names)
total_pages = (total_images - 1) // IMAGES_PER_PAGE + 1

st.subheader(f"👤 {selected_person}")
st.caption(f"{total_images} images • {total_pages} pages")

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

# ================= GRID DISPLAY ================= #
def fetch_preview(name):
    file_id = filename_to_id.get(name)
    if not file_id:
        return name, None
    try:
        return name, load_preview(file_id)
    except Exception:
        return name, None

cols = st.columns(3)

with st.spinner("Loading previews..."):
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(fetch_preview, name)
            for name in visible_images
        ]

        for idx, future in enumerate(as_completed(futures)):
            name, img = future.result()
            file_id = filename_to_id.get(name)

            with cols[idx % 3]:
                if img:
                    st.image(img, width='stretch')
                    img.close()

                    if file_id:
                        original_url = (
                            f"https://drive.google.com/file/d/{file_id}/view"
                        )
                        st.markdown(
                            f"[↗️ Open in Drive]({original_url})",
                            unsafe_allow_html=True
                        )
                else:
                    st.error("Failed to load")
