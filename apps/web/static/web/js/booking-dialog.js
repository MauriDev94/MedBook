// Booking dialog on the doctor's page (Paso 27). A slot link loads the
// booking form into <dialog id="booking-dialog"> with HTMX; this opens it as
// a modal. Closing needs no script: Esc and the method="dialog" forms do it,
// and the browser gives focus back to the slot that opened it.
document.addEventListener("htmx:afterSwap", (event) => {
  const target = event.detail.target;
  if (target instanceof HTMLDialogElement && !target.open) {
    target.showModal();
  }
});
