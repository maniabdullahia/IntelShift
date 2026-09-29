import api from "./api";
import useAuthStore from "../store/auth.store";

import Swal from "../components/shared/Alert";

const register = async (data) => {
    try {
        const response = await api.post("/register", data);
        // Email/password signups must verify their address (a link was emailed).
        // Social signups (Google/Facebook) arrive already verified, so no notice.
        const isSocial = data?.provider && data.provider !== "local";
        if (!isSocial) {
            Swal.fire({
                icon: 'success',
                title: 'Verification email sent',
                text: "Your account is ready. We've emailed you a verification link — please check your inbox (and spam) to verify your email.",
                confirmButtonColor: '#ff6b6b',
            });
        }
        console.log("User registered successfully:", response.data);
        return response.data;
    } catch (error) {
        const status = error.response?.status;
        if (status === 400) {
            Swal.fire({
                icon: 'error',
                title: 'Registration Failed',
                text: error.response?.data?.message || 'Invalid registration data. Please check your input and try again.',
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.response?.data?.message || 'An error occurred while registering. Please try again later.',
            });
        }
        throw new Error(error.response?.data?.message || "Error registering user");
    }
};

const login = async (data) => {
    try {
        const response = await api.post("/login", data);
        const { accessToken, user } = response.data;
        const { login: storeLogin } = useAuthStore.getState();
        storeLogin(user, accessToken);
        window.location.href = "/";
        return response.data;
    } catch (error) {
        const status = error.response?.status;
        if (status === 401) {
            Swal.fire({
                icon: 'error',
                title: 'Unauthorized',
                text: 'Invalid email or password. Please try again.',
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.response?.data?.message || 'An error occurred while logging in. Please try again later.',
            });
        }
        throw new Error(error.response?.data?.message || "Error logging in");
    }
};

const resetPassword = async (data) => {
    try {
        const response = await api.post("/reset-password", data);
        Swal.fire({
            icon: 'success',
            title: 'Password Reset Successful',
            text: 'Your password has been reset successfully. You can now log in with your new password.',
             confirmButtonColor: '#ff6b6b',
        });
        console.log("Password reset successfully:", response.data);
        return response.data;
    } catch (error) {
        const status = error.response?.status;
        if (status === 400) {
            Swal.fire({
                icon: 'error',
                title: 'Password Reset Failed',
                text: error.response?.data?.message || 'Invalid password reset data. Please check your input and try again.',
            });
        } else if (status === 403) {
            Swal.fire({
                icon: 'error',
                title: 'Password Reset Failed',
                text: error.response?.data?.message || 'The password reset token is invalid or has expired. Please request a new password reset.',
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.response?.data?.message || 'An error occurred while resetting your password. Please try again later.',
            });
        }
        throw new Error(error.response?.data?.message || "Error resetting password");
    }
}

const verifyEmail = async (data) => {
    try {
        const response = await api.post("/verify-email", data);
        Swal.fire({
            icon: 'success',
            title: 'Email Verification Successful',
            text: 'Your email has been verified successfully. You can now log in with your credentials.',
             confirmButtonColor: '#ff6b6b',
        });
        console.log("Email verified successfully:", response.data);
        return response.data;
    } catch (error) {
        const status = error.response?.status;
        if (status === 400) {    
            Swal.fire({
                icon: 'error',
                title: 'Email Verification Failed',
                text: error.response?.data?.message || 'Invalid email verification data. Please check your input and try again.',
            });           
        } else if (status === 403) {
            Swal.fire({
                icon: 'error',
                title: 'Email Verification Failed',
                text: error.response?.data?.message || 'The email verification token is invalid or has expired. Please request a new verification email.',
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.response?.data?.message || 'An error occurred while verifying your email. Please try again later.',
            });
        }
        throw new Error(error.response?.data?.message || "Error verifying email");
    }
}

const forgetPassword = async (data) => {
    try {
        const response = await api.post("/forget-password", data);
        Swal.fire({
            icon: 'success',
            title: 'Password Reset Link Sent',
            text: 'A password reset link has been sent to your email address. Please check your inbox and follow the instructions to reset your password.',
             confirmButtonColor: '#ff6b6b',
        });
        console.log("Password reset link sent successfully:", response.data);
        return response.data;
    } catch (error) {
        const status = error.response?.status;
        if (status === 400) {
            Swal.fire({
                icon: 'error',
                title: 'Password Reset Request Failed',
                text: error.response?.data?.message || 'Invalid password reset request data. Please check your input and try again.',
            });
        }
        else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.response?.data?.message || 'An error occurred while requesting a password reset. Please try again later.',
            });
        }
        throw new Error(error.response?.data?.message || "Error requesting password reset");
    }
};

const sendEmailVerificationLink = async (data) => {
    try {
        const response = await api.post("/email-verification-link", data);
        Swal.fire({
            icon: 'success',
            title: 'Email Verification Link Sent',
            text: 'A new email verification link has been sent to your email address. Please check your inbox and follow the instructions to verify your email.',
             confirmButtonColor: '#ff6b6b',
        });
        console.log("Email verification link sent successfully:", response.data);
        return response.data;
    }
    catch (error) {
        const status = error.response?.status;
        if (status === 400) {
            Swal.fire({
                icon: 'error',
                title: 'Email Verification Request Failed',
                text: error.response?.data?.message || 'Invalid email verification request data. Please check your input and try again.',
            });
        }
        else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.response?.data?.message || 'An error occurred while requesting a new email verification link. Please try again later.',
            });
        }
        throw new Error(error.response?.data?.message || "Error requesting email verification link");
    }
};


export {
    register,
    login,
    resetPassword,
    verifyEmail,
    sendEmailVerificationLink,
    forgetPassword
}