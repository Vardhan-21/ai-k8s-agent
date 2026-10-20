"use client";

import { useEffect, useState } from "react";
import { insforge } from "@/services/insforge";

export interface User {
  id: string;
  email: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState<string | null>(null);

  useEffect(() => {
    // Check initial user session from InsForge and persisted storage
    async function checkSession() {
      try {
        if (typeof window === "undefined") return;

        const savedPending = localStorage.getItem("insforge_pending_email");
        if (savedPending) {
          setPendingVerificationEmail(savedPending);
        }

        const savedToken = localStorage.getItem("insforge_auth_token");
        const savedUser = localStorage.getItem("insforge_auth_user");

        if (!savedToken) {
          // No saved session — user is definitely unauthenticated, show login immediately
          setLoading(false);
          return;
        }

        // Restore saved session immediately
        try {
          const parsed = JSON.parse(savedUser || "{}");
          if (parsed.id) {
            setUser(parsed);
            setToken(savedToken);
          }
        } catch {
          // ignore
        }

        // Verify active session with InsForge in the background
        const { data, error: userError } = await insforge.auth.getCurrentUser();
        if (data?.user) {
          setUser({ id: data.user.id, email: data.user.email });
          const activeToken =
            (insforge.auth as any).tokenManager?.getAccessToken() || savedToken;
          setToken(activeToken);
        } else if (userError) {
          // Token expired or revoked
          localStorage.removeItem("insforge_auth_token");
          localStorage.removeItem("insforge_auth_user");
          setUser(null);
          setToken(null);
        }
      } catch (err: any) {
        console.error("Session check error:", err);
      } finally {
        setLoading(false);
      }
    }

    checkSession();
  }, []);

  const signIn = async (email: string, password: string) => {
    setError(null);
    setLoading(true);
    try {
      const { data, error: signInError } = await insforge.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) {
        setError(signInError.message || "Invalid credentials");
        return { success: false, error: signInError.message };
      }

      if (data?.user && data.accessToken) {
        const u = { id: data.user.id, email: data.user.email };
        setUser(u);
        setToken(data.accessToken);
        setPendingVerificationEmail(null);
        if (typeof window !== "undefined") {
          localStorage.removeItem("insforge_pending_email");
          localStorage.setItem("insforge_auth_token", data.accessToken);
          localStorage.setItem("insforge_auth_user", JSON.stringify(u));
        }
        return { success: true };
      }

      setError("Failed to establish session");
      return { success: false, error: "Failed to establish session" };
    } catch (err: any) {
      setError(err.message || "Sign in failed");
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  };

  const signUp = async (email: string, password: string) => {
    setError(null);
    setLoading(true);
    try {
      const { data, error: signUpError } = await insforge.auth.signUp({
        email,
        password,
      });

      if (signUpError) {
        setError(signUpError.message || "Sign up failed");
        return { success: false, error: signUpError.message };
      }

      // If email verification is required by InsForge
      if (data?.requireEmailVerification) {
        setPendingVerificationEmail(email);
        if (typeof window !== "undefined") {
          localStorage.setItem("insforge_pending_email", email);
        }
        return { success: true, requireVerification: true, email };
      }

      // If session established immediately (e.g. email verification disabled)
      if (data?.accessToken && data.user) {
        const u = { id: data.user.id, email: data.user.email };
        setUser(u);
        setToken(data.accessToken);
        setPendingVerificationEmail(null);
        if (typeof window !== "undefined") {
          localStorage.removeItem("insforge_pending_email");
          localStorage.setItem("insforge_auth_token", data.accessToken);
          localStorage.setItem("insforge_auth_user", JSON.stringify(u));
        }
        return { success: true };
      } else {
        // Fallback: try direct sign in
        return await signIn(email, password);
      }
    } catch (err: any) {
      setError(err.message || "Sign up failed");
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  };

  const verifyEmail = async (email: string, otp: string) => {
    setError(null);
    setLoading(true);
    const cleanEmail = email.trim();
    const cleanOtp = otp.trim().replace(/\D/g, "");
    try {
      // 1. Try verifyOtp (login OTP / passwordless session)
      const otpRes = await insforge.auth.verifyOtp({
        email: cleanEmail,
        otp: cleanOtp,
      });

      if (otpRes.data?.user && otpRes.data?.accessToken) {
        const u = { id: otpRes.data.user.id, email: otpRes.data.user.email };
        setUser(u);
        setToken(otpRes.data.accessToken);
        setPendingVerificationEmail(null);
        if (typeof window !== "undefined") {
          localStorage.removeItem("insforge_pending_email");
          localStorage.setItem("insforge_auth_token", otpRes.data.accessToken);
          localStorage.setItem("insforge_auth_user", JSON.stringify(u));
        }
        return { success: true };
      }

      // 2. Try verifyEmail (signup email verification code)
      const { data, error: verifyErr } = await insforge.auth.verifyEmail({
        email: cleanEmail,
        otp: cleanOtp,
      });

      if (!verifyErr && data?.user && data.accessToken) {
        const u = { id: data.user.id, email: data.user.email };
        setUser(u);
        setToken(data.accessToken);
        setPendingVerificationEmail(null);
        if (typeof window !== "undefined") {
          localStorage.removeItem("insforge_pending_email");
          localStorage.setItem("insforge_auth_token", data.accessToken);
          localStorage.setItem("insforge_auth_user", JSON.stringify(u));
        }
        return { success: true };
      }

      const msg =
        verifyErr?.message ||
        otpRes.error?.message ||
        "Invalid or expired verification code. Please check the code or request a new one.";
      setError(msg);
      return { success: false, error: msg };
    } catch (err: any) {
      const msg = err.message || "Failed to verify code";
      setError(msg);
      return { success: false, error: msg };
    } finally {
      setLoading(false);
    }
  };

  const sendLoginOtp = async (email: string) => {
    setError(null);
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      return { success: false, error: "Email is required" };
    }
    try {
      const { data, error: otpErr } = await insforge.auth.signInWithOtp({
        email: cleanEmail,
      });

      if (otpErr) {
        return {
          success: false,
          error: otpErr.message || "Failed to send login code",
        };
      }

      setPendingVerificationEmail(cleanEmail);
      if (typeof window !== "undefined") {
        localStorage.setItem("insforge_pending_email", cleanEmail);
      }

      return {
        success: true,
        message: data?.message || `6-digit login code sent to ${cleanEmail}!`,
      };
    } catch (err: any) {
      return {
        success: false,
        error: err.message || "Failed to send login code",
      };
    }
  };

  const resendVerificationEmail = async (email: string) => {
    try {
      const { data, error: resendErr } = await insforge.auth.resendVerificationEmail({
        email,
      });

      if (resendErr) {
        return {
          success: false,
          error: resendErr.message || "Failed to resend verification code",
        };
      }

      return {
        success: true,
        message:
          data?.message ||
          "Verification code sent! Please check your email inbox.",
      };
    } catch (err: any) {
      return {
        success: false,
        error: err.message || "Failed to resend verification email",
      };
    }
  };

  const clearPendingVerification = () => {
    setPendingVerificationEmail(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("insforge_pending_email");
    }
  };

  const signOut = async () => {
    setLoading(true);
    try {
      await insforge.auth.signOut();
    } catch (err: any) {
      console.error("Sign out error:", err);
    } finally {
      if (typeof window !== "undefined") {
        localStorage.removeItem("insforge_auth_token");
        localStorage.removeItem("insforge_auth_user");
        localStorage.removeItem("insforge_pending_email");
      }
      setUser(null);
      setToken(null);
      setPendingVerificationEmail(null);
      setLoading(false);
    }
  };

  return {
    user,
    token,
    loading,
    error,
    pendingVerificationEmail,
    signIn,
    signUp,
    verifyEmail,
    resendVerificationEmail,
    sendLoginOtp,
    clearPendingVerification,
    signOut,
  };
}
