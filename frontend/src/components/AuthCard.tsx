"use client";

import { useEffect, useState, useRef } from "react";

interface AuthCardProps {
  onSignIn: (
    email: string,
    pass: string
  ) => Promise<{ success: boolean; error?: string; requireVerification?: boolean }>;
  onSignUp: (
    email: string,
    pass: string
  ) => Promise<{
    success: boolean;
    error?: string;
    requireVerification?: boolean;
    email?: string;
  }>;
  onVerifyEmail: (
    email: string,
    otp: string
  ) => Promise<{ success: boolean; error?: string }>;
  onResendVerification: (
    email: string
  ) => Promise<{ success: boolean; error?: string; message?: string }>;
  onSendLoginOtp?: (
    email: string
  ) => Promise<{ success: boolean; error?: string; message?: string }>;
  pendingEmail?: string | null;
  onCancelVerification?: () => void;
}

export function AuthCard({
  onSignIn,
  onSignUp,
  onVerifyEmail,
  onResendVerification,
  onSendLoginOtp,
  pendingEmail,
  onCancelVerification,
}: AuthCardProps) {
  // Modes: "verify" (Enter Code), "signin" (Password), "signup" (Create Account)
  const [mode, setMode] = useState<"verify" | "signin" | "signup">(
    pendingEmail ? "verify" : "signin"
  );
  const [email, setEmail] = useState(pendingEmail || "");
  const [password, setPassword] = useState("");
  
  // 6 separate slots for the OTP
  const [otpSlots, setOtpSlots] = useState<string[]>(["", "", "", "", "", ""]);
  
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  const slotRefs = useRef<(HTMLInputElement | null)[]>([]);

  // If pending email is set, auto-switch to code mode
  useEffect(() => {
    if (pendingEmail) {
      setEmail(pendingEmail);
      setMode("verify");
      setInfoMessage(`Verification code sent to ${pendingEmail}. Please enter the 6 digits below.`);
    }
  }, [pendingEmail]);

  // Try to load any saved pending email on mount
  useEffect(() => {
    if (typeof window !== "undefined" && !pendingEmail) {
      const savedEmail = localStorage.getItem("insforge_pending_email");
      if (savedEmail) {
        setEmail(savedEmail);
        setMode("verify");
        setInfoMessage(`Enter the 6-digit code sent to ${savedEmail}`);
      }
    }
  }, [pendingEmail]);

  // Focus the first empty slot when switching to verify mode
  useEffect(() => {
    if (mode === "verify") {
      setTimeout(() => {
        const firstEmpty = otpSlots.findIndex((s) => !s);
        const targetIdx = firstEmpty === -1 ? 0 : firstEmpty;
        slotRefs.current[targetIdx]?.focus();
      }, 100);
    }
  }, [mode]);

  // Resend countdown timer
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  // Handle single slot input change
  const handleSlotChange = (index: number, val: string) => {
    // Digits only
    const digits = val.replace(/\D/g, "");
    if (!digits) {
      const updated = [...otpSlots];
      updated[index] = "";
      setOtpSlots(updated);
      return;
    }

    // If pasted or multiple digits entered
    if (digits.length > 1) {
      handlePastedCode(digits);
      return;
    }

    // Single digit entry
    const updated = [...otpSlots];
    updated[index] = digits;
    setOtpSlots(updated);

    // Auto-advance to next slot
    if (index < 5) {
      slotRefs.current[index + 1]?.focus();
    }
  };

  // Handle backspace navigation
  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      if (!otpSlots[index] && index > 0) {
        slotRefs.current[index - 1]?.focus();
      }
    } else if (e.key === "ArrowLeft" && index > 0) {
      slotRefs.current[index - 1]?.focus();
    } else if (e.key === "ArrowRight" && index < 5) {
      slotRefs.current[index + 1]?.focus();
    }
  };

  // Handle pasting full 6-digit code
  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasteData = e.clipboardData.getData("text");
    handlePastedCode(pasteData);
  };

  const handlePastedCode = (text: string) => {
    const digits = text.replace(/\D/g, "").slice(0, 6).split("");
    const updated = ["", "", "", "", "", ""];
    digits.forEach((d, i) => {
      if (i < 6) updated[i] = d;
    });
    setOtpSlots(updated);

    const focusIdx = Math.min(digits.length, 5);
    slotRefs.current[focusIdx]?.focus();
  };

  const fullOtp = otpSlots.join("");

  const handleSubmitAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }
    setError(null);
    setInfoMessage(null);
    setLoading(true);

    if (mode === "signup") {
      const res = await onSignUp(email, password);
      setLoading(false);
      if (res.requireVerification) {
        setMode("verify");
        setInfoMessage(
          `We sent a 6-digit verification code to ${email}. Please enter the code below to complete login.`
        );
      } else if (!res.success) {
        setError(res.error || "Sign up failed");
      }
    } else {
      const res = await onSignIn(email, password);
      setLoading(false);
      if (res.requireVerification) {
        setMode("verify");
        setInfoMessage(
          `Your email requires verification. Enter the 6-digit code sent to ${email}.`
        );
      } else if (!res.success) {
        setError(res.error || "Sign in failed");
      }
    }
  };

  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setError("Please provide your email address.");
      return;
    }

    if (fullOtp.length !== 6) {
      setError("Please enter all 6 digits of your verification code.");
      return;
    }

    setError(null);
    setInfoMessage(null);
    setLoading(true);

    const res = await onVerifyEmail(cleanEmail, fullOtp);
    setLoading(false);

    if (!res.success) {
      setError(
        res.error ||
          "Invalid or expired verification code. Please check the code in your email or click Resend."
      );
    }
  };

  const handleResendCode = async () => {
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setError("Please enter your email above before requesting a new code.");
      return;
    }
    if (resending || resendCooldown > 0) return;

    setError(null);
    setInfoMessage(null);
    setResending(true);

    let res: { success: boolean; error?: string; message?: string };
    if (onSendLoginOtp) {
      res = await onSendLoginOtp(cleanEmail);
    } else {
      res = await onResendVerification(cleanEmail);
    }
    setResending(false);

    if (res.success) {
      setInfoMessage(
        res.message ||
          `A new 6-digit code has been sent to ${cleanEmail}. Check your inbox or spam.`
      );
      setResendCooldown(45);
    } else {
      setError(res.error || "Failed to send code. Please try again.");
    }
  };

  return (
    <div className="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-900/90 p-8 shadow-2xl backdrop-blur-xl">
      {/* 3 Prominent Navigation Tabs */}
      <div className="grid grid-cols-3 gap-1 rounded-xl bg-gray-950 p-1 border border-gray-800 mb-6">
        <button
          type="button"
          onClick={() => {
            setMode("verify");
            setError(null);
            setInfoMessage(null);
          }}
          className={`flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition ${
            mode === "verify"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
              : "text-indigo-400 hover:text-white"
          }`}
        >
          <span>Enter Code</span>
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        </button>

        <button
          type="button"
          onClick={() => {
            setMode("signin");
            setError(null);
            setInfoMessage(null);
          }}
          className={`rounded-lg py-2 text-xs font-semibold transition ${
            mode === "signin"
              ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
              : "text-gray-400 hover:text-white"
          }`}
        >
          Password
        </button>

        <button
          type="button"
          onClick={() => {
            setMode("signup");
            setError(null);
            setInfoMessage(null);
          }}
          className={`rounded-lg py-2 text-xs font-semibold transition ${
            mode === "signup"
              ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
              : "text-gray-400 hover:text-white"
          }`}
        >
          Sign Up
        </button>
      </div>

      {/* Header Info */}
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
          {mode === "verify" ? (
            <svg
              className="h-6 w-6 text-indigo-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
          ) : (
            <svg
              className="h-6 w-6 text-blue-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
          )}
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          {mode === "verify"
            ? "Enter 6-Digit Code"
            : mode === "signup"
            ? "Create SRE Account"
            : "Sign In with Password"}
        </h2>
        <p className="mt-1 text-sm text-gray-400">
          {mode === "verify"
            ? "Enter the 6-digit code received in your email to log in."
            : "InsForge-authenticated Kubernetes troubleshooting"}
        </p>
      </div>

      {/* Alert Messages */}
      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-950/40 p-3 text-xs text-red-300">
          <p>{error}</p>
        </div>
      )}

      {infoMessage && (
        <div className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-950/40 p-3 text-xs text-emerald-300">
          {infoMessage}
        </div>
      )}

      {/* MODE 1: 6-DIGIT CODE ENTRY SLOTS (VERIFY / EMAIL OTP) */}
      {mode === "verify" ? (
        <form onSubmit={handleVerifyCode} className="space-y-6">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">
              Your Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="engineer@company.com"
              required
              className="w-full rounded-lg border border-gray-800 bg-gray-950 px-3.5 py-2.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400">
                Enter 6-Digit Code Slots
              </label>
              <span className="text-[11px] text-indigo-400 font-medium">
                Check inbox or spam
              </span>
            </div>

            {/* 6 Individual Distinct Slot Boxes */}
            <div className="flex items-center justify-between gap-2">
              {otpSlots.map((digit, idx) => (
                <input
                  key={idx}
                  ref={(el) => {
                    slotRefs.current[idx] = el;
                  }}
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleSlotChange(idx, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(idx, e)}
                  onPaste={handlePaste}
                  className="w-12 h-14 text-center font-mono text-2xl font-bold rounded-xl border-2 border-gray-700 bg-gray-950 text-white placeholder-gray-600 focus:border-indigo-400 focus:bg-indigo-950/30 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition shadow-inner"
                />
              ))}
            </div>

            <p className="mt-2 text-center text-xs text-gray-400">
              Paste or type your 6-digit code directly into the slots above
            </p>
          </div>

          <button
            type="submit"
            disabled={loading || fullOtp.length !== 6 || !email.trim()}
            className="w-full rounded-xl bg-indigo-600 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 transition hover:bg-indigo-500 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                <span>Verifying Code & Logging In...</span>
              </span>
            ) : (
              "Verify Code & Log In →"
            )}
          </button>

          <div className="pt-2 flex items-center justify-between text-xs border-t border-gray-800/60">
            <button
              type="button"
              onClick={handleResendCode}
              disabled={resending || resendCooldown > 0 || !email.trim()}
              className="text-indigo-400 hover:text-indigo-300 disabled:opacity-40 disabled:hover:text-indigo-400 transition"
            >
              {resending
                ? "Sending code..."
                : resendCooldown > 0
                ? `Resend code in ${resendCooldown}s`
                : "Resend Code to Email"}
            </button>

            <button
              type="button"
              onClick={() => {
                setMode("signin");
                setError(null);
                setInfoMessage(null);
                if (onCancelVerification) {
                  onCancelVerification();
                }
              }}
              className="text-gray-400 hover:text-white transition"
            >
              Use Password Instead
            </button>
          </div>
        </form>
      ) : (
        /* MODE 2 & 3: PASSWORD LOGIN & SIGNUP */
        <form onSubmit={handleSubmitAuth} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="engineer@company.com"
              required
              className="w-full rounded-lg border border-gray-800 bg-gray-950 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full rounded-lg border border-gray-800 bg-gray-950 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            {loading
              ? "Processing..."
              : mode === "signup"
              ? "Create Account & Send Code"
              : "Sign In with Password"}
          </button>

          {/* Direct callout to Enter Code */}
          <div className="pt-3">
            <button
              type="button"
              onClick={() => {
                setMode("verify");
                setError(null);
                setInfoMessage(null);
              }}
              className="w-full rounded-lg border border-indigo-500/30 bg-indigo-950/20 py-2.5 px-3 text-xs text-indigo-300 hover:bg-indigo-950/40 hover:text-white transition flex items-center justify-center gap-2"
            >
              <span>📩 Got a 6-digit code in your email?</span>
              <span className="font-semibold underline">Enter code here →</span>
            </button>
          </div>

          <div className="mt-4 text-center text-xs text-gray-400 border-t border-gray-800/60 pt-4">
            {mode === "signup" ? (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setMode("signin");
                    setError(null);
                    setInfoMessage(null);
                  }}
                  className="text-blue-400 underline hover:text-blue-300"
                >
                  Sign in with password
                </button>
              </>
            ) : (
              <>
                Don&apos;t have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setMode("signup");
                    setError(null);
                    setInfoMessage(null);
                  }}
                  className="text-blue-400 underline hover:text-blue-300"
                >
                  Sign up
                </button>
              </>
            )}
          </div>
        </form>
      )}
    </div>
  );
}