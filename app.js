const gallery = document.getElementById("gallery");
const searchBox = document.getElementById("searchBox");
const toggleBtn = document.getElementById("toggleLookup");
const lookupSection = document.getElementById("lookupSection");
const loadMoreBtn = document.getElementById("loadMoreBtn");
const personList = document.getElementById("personList");

const IMAGES_PER_BATCH = 35;

let faceDirectory = {};
let driveIndex = {};
let visibleCount = IMAGES_PER_BATCH;

Promise.all([
  fetch("face_directory.json").then(r => r.json()),
  fetch("drive_index.json").then(r => r.json())
]).then(([faces, drive]) => {
  faceDirectory = faces;
  driveIndex = drive;
  populateDatalist();
  render();
});

// Populate dropdown suggestions
function populateDatalist() {
  Object.keys(faceDirectory)
    .sort()
    .forEach(person => {
      const option = document.createElement("option");
      option.value = person;
      personList.appendChild(option);
    });
}

// Search handler
searchBox.addEventListener("input", () => {
  visibleCount = IMAGES_PER_BATCH;
  render();
});

// Show / Hide face lookup
toggleBtn.onclick = () => {
  lookupSection.classList.toggle("hidden");
  toggleBtn.textContent = lookupSection.classList.contains("hidden")
    ? "Show face reference"
    : "Hide face reference";
};

// Load more
loadMoreBtn.onclick = () => {
  visibleCount += IMAGES_PER_BATCH;
  render();
};

function render() {
  gallery.innerHTML = "";

  const filter = searchBox.value.toLowerCase();
  let rendered = 0;

  Object.entries(faceDirectory).forEach(([person, images]) => {
    if (!person.toLowerCase().includes(filter)) return;

    images.forEach(filename => {
      // 🚫 Skip face preview images
      if (filename.toLowerCase() === "face_preview.jpg") return;

      if (rendered >= visibleCount) return;

      const fileId = driveIndex[filename];
      const card = document.createElement("div");
      card.className = "card";

      if (!fileId) {
        card.appendChild(missingEntry(filename));
        gallery.appendChild(card);
        rendered++;
        return;
      }

      const img = document.createElement("img");
      img.loading = "lazy";
      img.src = `https://drive.google.com/thumbnail?id=${fileId}&sz=w1200`;

      img.onerror = () => {
        img.replaceWith(fallbackLink(fileId, filename));
      };

      const link = document.createElement("a");
      link.href = `https://drive.google.com/file/d/${fileId}/view`;
      link.target = "_blank";
      link.textContent = "↗ Open full-resolution image in Google Drive";

      card.appendChild(img);
      card.appendChild(link);
      gallery.appendChild(card);
      rendered++;
    });
  });

  loadMoreBtn.style.display = rendered >= visibleCount ? "block" : "none";
}

// ---------- Helpers ----------

function fallbackLink(fileId, filename) {
  const a = document.createElement("a");
  a.href = `https://drive.google.com/file/d/${fileId}/view`;
  a.target = "_blank";
  a.textContent = `Thumbnail unavailable — open ${filename}`;
  a.style.padding = "16px";
  a.style.display = "block";
  return a;
}

function missingEntry(filename) {
  const div = document.createElement("div");
  div.style.padding = "16px";
  div.style.color = "#999";
  div.textContent = `Missing Drive ID for ${filename}`;
  return div;
}

