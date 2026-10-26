// Dialogs that HTMX fills: booking on the doctor's page (Paso 27) and
// cancelling in "My appointments" (Paso 28). A link loads its content into a
// <dialog> and this opens it as a modal. When a form inside the dialog
// updates the page behind it instead (a cancelled appointment's status), the
// dialog has done its job and closes, and the focus moves to what the form
// updated: the link that opened the dialog was in the replaced content, so
// the browser has nothing to give it back to (Paso 29). Closing needs no
// other script: Esc and the method="dialog" forms do it, and the browser
// gives focus back to the link that opened it.
document.addEventListener("htmx:afterSwap", (event) => {
  const target = event.detail.target;
  if (target instanceof HTMLDialogElement) {
    if (!target.open) {
      target.showModal();
    }
    return;
  }
  // event.target is the new content; detail.target, what it replaced
  const dialog = event.detail.requestConfig?.elt?.closest("dialog");
  if (dialog && !dialog.contains(event.target)) {
    dialog.close();
    event.target.focus();
  }
});
