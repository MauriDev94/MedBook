// Dialogs that HTMX fills: booking on the doctor's page (Paso 27) and
// cancelling in "My appointments" (Paso 28). A link loads its content into a
// <dialog> and this opens it as a modal. When a form inside the dialog
// updates the page behind it instead (a cancelled appointment's status), the
// dialog has done its job and closes. Closing needs no other script: Esc and
// the method="dialog" forms do it, and the browser gives focus back to the
// link that opened it.
document.addEventListener("htmx:afterSwap", (event) => {
  const target = event.detail.target;
  if (target instanceof HTMLDialogElement) {
    if (!target.open) {
      target.showModal();
    }
    return;
  }
  event.detail.requestConfig?.elt?.closest("dialog")?.close();
});
