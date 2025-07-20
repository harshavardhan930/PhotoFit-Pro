function previewImage() {
  const photo = document.getElementById("photo").files[0];
  const preview = document.getElementById("preview");

  if (photo) {
    preview.src = URL.createObjectURL(photo);
    preview.style.display = 'block';
  }
}

function submitForm() {
  const bgColor = document.getElementById("bgColor").value;
  const photoCount = document.getElementById("photoCount").value;

  // Simulate generation (replace this with real canvas drawing or backend call)
  alert(`Generating card with ${photoCount} photos and background color ${bgColor}`);

  // Show download link (simulate for now)
  const downloadBtn = document.getElementById("downloadBtn");
  downloadBtn.href = "#"; // Replace with actual generated image URL
  downloadBtn.style.display = "inline-block";
  downloadBtn.textContent = "Download Output";
}
