import React from "react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "success";
  size?: "sm" | "md" | "lg";
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = "primary",
  size = "md",
  className = "",
  ...props
}) => {
  const baseStyles = "inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none disabled:opacity-50";
  const sizeStyles = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base",
  }[size];

  const variantStyles = {
    primary: "bg-sky-600 hover:bg-sky-700 text-white",
    secondary: "bg-slate-700 hover:bg-slate-600 text-slate-100",
    danger: "bg-rose-600 hover:bg-rose-700 text-white",
    success: "bg-emerald-600 hover:bg-emerald-700 text-white",
  }[variant];

  return (
    <button className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`} {...props}>
      {children}
    </button>
  );
};

export const Card: React.FC<{ title?: string; children: React.ReactNode; className?: string }> = ({
  title,
  children,
  className = "",
}) => (
  <div className={`bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm ${className}`}>
    {title && <h3 className="text-lg font-semibold text-slate-100 mb-4">{title}</h3>}
    {children}
  </div>
);

export const Loading: React.FC<{ message?: string }> = ({ message = "Loading..." }) => (
  <div className="flex flex-col items-center justify-center p-8 space-y-3">
    <div className="w-8 h-8 border-4 border-sky-500 border-t-transparent rounded-full animate-spin" />
    <span className="text-sm text-slate-400">{message}</span>
  </div>
);

export const Modal: React.FC<{ isOpen: boolean; onClose: () => void; title: string; children: React.ReactNode }> = ({
  isOpen,
  onClose,
  title,
  children,
}) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full p-6 shadow-2xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold text-slate-100">{title}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">&times;</button>
        </div>
        {children}
      </div>
    </div>
  );
};

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error: string | null }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-200">
          <h4 className="font-bold mb-2">Something went wrong</h4>
          <p className="text-sm">{this.state.error}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
