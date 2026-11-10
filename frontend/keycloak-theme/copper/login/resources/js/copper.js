document.querySelectorAll('form').forEach((form) => {
  form.addEventListener('submit', () => {
    if (!form.checkValidity()) return;
    form.querySelectorAll('button[type="submit"]').forEach((button) => {
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
    });
  });
});
