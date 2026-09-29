import Swal from "sweetalert2";

const Alert = Swal.mixin({
  customClass: {
    popup: "compana-swal-popup",
    title: "compana-swal-title",
    htmlContainer: "compana-swal-text",
    confirmButton: "compana-swal-confirm",
    cancelButton: "compana-swal-cancel",
    actions: "compana-swal-actions",
  },
  buttonsStyling: false,
  reverseButtons: true,
  heightAuto: false,
  confirmButtonText: "OK",
});

export const showAlert = (options) => Alert.fire(options);

export const showSuccess = (title, text, options = {}) =>
  Alert.fire({
    icon: "success",
    title,
    text,
    ...options,
  });

export const showError = (title, text, options = {}) =>
  Alert.fire({
    icon: "error",
    title,
    text,
    ...options,
  });

export const showWarning = (title, text, options = {}) =>
  Alert.fire({
    icon: "warning",
    title,
    text,
    ...options,
  });

export const showInfo = (title, text, options = {}) =>
  Alert.fire({
    icon: "info",
    title,
    text,
    ...options,
  });

export const showConfirm = ({
  title = "Are you sure?",
  text,
  confirmButtonText = "Yes",
  cancelButtonText = "Cancel",
  ...options
} = {}) =>
  Alert.fire({
    icon: "question",
    title,
    text,
    showCancelButton: true,
    confirmButtonText,
    cancelButtonText,
    ...options,
  });

export const showToast = ({
  icon = "success",
  title,
  position = "top-end",
  timer = 2200,
  ...options
} = {}) =>
  Alert.fire({
    toast: true,
    icon,
    title,
    position,
    showConfirmButton: false,
    timer,
    timerProgressBar: true,
    ...options,
  });

export default Alert;
