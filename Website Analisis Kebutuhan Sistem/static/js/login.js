// Tampilkan / sembunyikan kata sandi.
const passwordInput = document.getElementById("password");
document.getElementById("toggle-password").addEventListener("click", () => {
  passwordInput.type = passwordInput.type === "password" ? "text" : "password";
});
