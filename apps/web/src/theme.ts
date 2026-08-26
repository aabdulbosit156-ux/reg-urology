import { createTheme } from "flowbite-react";

export const regurologTheme = createTheme({
  button: {
    color: {
      primary:
        "border border-transparent bg-brand-700 text-white hover:bg-brand-800 focus:ring-4 focus:ring-brand-100",
      secondary:
        "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus:ring-4 focus:ring-slate-100",
    },
  },
  badge: {
    root: {
      color: {
        primary: "bg-brand-50 text-brand-800",
      },
    },
  },
});
