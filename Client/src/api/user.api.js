import api from "./api";
import useAuthStore from "../store/auth.store";
import useWorkspaceStore from "../store/workspace.store";
import Swal from "../components/shared/Alert";

const logout = async (showConfirmation) => {
  const res = await api.post("/logout");
  const status = res.status;

  if (status === 200) {
    const { logout: storeLogout } = useAuthStore.getState();
    storeLogout();
    useWorkspaceStore.getState().clearStorage();
    if(showConfirmation){
      Swal.fire({
      icon: "success",
      title: "Logged Out",
      text: "You have been logged out successfully.",
      confirmButtonColor: "#ff6b6b",
    }).then(() => {
      window.location.href = "/login";
    });
    } else {
      window.location.href = "/login"
    }
  } else {
    Swal.fire({
      icon: "error",
      title: "Logout Failed",
      text: "An error occurred while logging out. Please try again later.",
    });
  }
};

const getProfile = async () => {
  try {
    const response = await api.get("/profile");
    return response.data;
  } catch (error) {
    if(error.status == 401) {
      await logout()
    }
    throw new Error(
      error.response?.data?.message || "Error fetching user profile",
    );
  }
};

const updateProfile = async (data) => {
  try {
    const response = await api.put("/profile", data);
    Swal.fire({
      icon: "success",
      title: "Profile Updated",
      text: "Your profile has been updated successfully.",
    });
    return response.data;
  } catch (error) {
    Swal.fire({
      icon: "error",
      title: "Error",
      text: error.response?.data?.message || "Error updating user profile",
      confirmButtonColor: "#ff6b6b",
    });
    throw new Error(
      error.response?.data?.message || "Error updating user profile",
    );
  }
};

const deleteAccount = async () => {
  try {
    const response = await api.delete("/profile");
    const { logout: storeLogout } = useAuthStore.getState();
    storeLogout();
    useWorkspaceStore.getState().clearStorage();
    Swal.fire({
      icon: "success",
      title: "Account Deleted",
      text: "Your account has been deleted successfully.",
      confirmButtonColor: "#ff6b6b",
    }).then(() => {
      window.location.href = "/register";
    });
    return response.data;
  } catch (error) {
    const status = error.response?.status;
    if (status === 404) {
      Swal.fire({
        icon: "error",
        title: "User Not Found",
        text: "The user account could not be found. It may have already been deleted.",
      });
    } else {
      Swal.fire({
        icon: "error",
        title: "Error",
        text:
          error.response?.data?.message ||
          "An error occurred while deleting the account. Please try again later.",
          confirmButtonColor: "#ff6b6b",
      });
    }
    throw new Error(
      error.response?.data?.message || "Error deleting user account",
    );
  }
};

const changePassword = async (currentPassword, newPassword) => {
  try {
    const response = await api.post("/change-password", {
      currentPassword,
      newPassword,
    });
    Swal.fire({
      icon: "success",
      title: "Password Changed",
      text: "Your password has been changed successfully.",
    });
    return response.data;
  } catch (error) {
    Swal.fire({
      icon: "error",
      title: "Error",
      text:
        error.response?.data?.message ||
        "An error occurred while changing the password. Please try again later.",
        confirmButtonColor: "#ff6b6b",
    });
    throw new Error(error.response?.data?.message || "Error changing password");
  }
};

// starter, growth, pro, trial
const changePlan = async (planId, subscriptionId, priceId) => {
  try {
    if (!planId || !subscriptionId || !priceId) {
      Swal.fire({
        icon: "error",
        title: "Missing Information",
        text: "Please provide planId, subscriptionId, and priceId to change the plan.",
        confirmButtonColor: "#ff6b6b",
      });
      return;
    }
    const response = await api.post("/change-plan", { planId, subscriptionId, priceId });
    console.log("Plan change response:", response.data);
    Swal.fire({
      icon: "success",
      title: "Plan Changed",
      text: "Your subscription plan has been changed successfully.",
      confirmButtonColor: "#ff6b6b",
    });
    return response.data;
  }
  catch (error) {
    Swal.fire({
      icon: "error",
      title: "Error",
      text: error.response?.data?.message ||
        "An error occurred while changing the subscription plan. Please try again later.",
      confirmButtonColor: "#ff6b6b",
    });
  }
};

const updateAlertSettings = async (payload) => {
  try {
    const response = await api.put("/settings/alerts", payload);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.message || "Error updating alert settings");
  }
};

const sendTestAlert = async () => {
  try {
    const response = await api.post("/alerts/test");
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.message || "Error sending test alert");
  }
};

  export { logout, getProfile, updateProfile, updateAlertSettings, sendTestAlert, deleteAccount, changePassword, changePlan };
