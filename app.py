import streamlit as st
import pickle
import io
import os
import requests
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===================== CONFIG ===================== #
FACE_PKL_PATH = "face_directory.pkl"
DRIVE_INDEX_PATH = "drive_index.pkl"
LOOKUP_IMAGE_PATH = "faceLookup.jpg"

PREVIEW_SIZE = (320, 320)   # display preview only
IMAGES_PER_PAGE = 12        # hard cap for stability
MAX_WORKERS = 2             # critical for multi-user safety
CACHE_DIR = ".preview_cache"
# ================================================= #

os.makedirs(CACHE_DIR, exist_ok=True)

st.set_page_config(
    page_title="Face Sorted Image Viewer",
    layout="wide"
)

st.title("📸 Face-Sorted Image Viewer")

# ===================== LOAD METADATA ===================== #
@st.cache_resource
def load_drive_index():
    with open(DRIVE_INDEX_PATH, "rb") as f:
        return pickle.load(f)

@st.cache_resource
def load_face_directory():
    with open(FACE_PKL_PATH, "rb") as f:
        return pickle.load(f)

filename_to_id = load_drive_index()
face_directory = load_face_directory()

# ===================== PREVIEW LOADER ===================== #
def load_preview(file_id):
    """
    Disk-only cache, no Streamlit cache.
    Safe for multi-user usage.
    """
    cache_path = os.path.join(CACHE_DIR, f"{file_id}.png")

    if os.path.exists(cache_path):
        return Image.open(cache_path)

    url = f"https://drive.google.com/uc?id={file_id}"
    r = requests.get(url, timeout=8)
    r.raise_for_status()

    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    img.thumbnail(PREVIEW_SIZE)  # preview only
    img.save(cache_path, format="PNG")

    return Image.open(cache_path)

# ===================== SIDEBAR ===================== #
st.sidebar.header("Navigation")

people = sorted(face_directory.keys())
default_person = max(people, key=lambda k: len(face_directory[k]))

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

# ===================== PAGINATION ===================== #
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

# ===================== GRID DISPLAY ===================== #
def fetch_preview(name):
    file_id = filename_to_id.get(name)
    if not file_id:
        return name, None, None

    try:
        img = load_preview(file_id)
        return name, img, file_id
    except Exception:
        return name, None, file_id

cols = st.columns(3)

with st.spinner("Loading images..."):
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(fetch_preview, name)
            for name in visible_images
        ]

        for idx, future in enumerate(as_completed(futures)):
            name, img, file_id = future.result()

            with cols[idx % 3]:
                if img:
                    st.image(img, width='stretch')
                    img.close()

                    if file_id:
                        drive_url = (
                            f"https://drive.google.com/file/d/{file_id}/view"
                        )
                        st.markdown(
                            f"[↗️ Open in Drive]({drive_url})",
                            unsafe_allow_html=True
                        )
                else:
                    st.error("Preview unavailable")
