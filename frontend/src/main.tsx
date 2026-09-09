import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { AdminLayout } from "@/components/layout/admin-layout";
import { LoginPage } from "@/pages/login-page";
import { NotFound } from "@/pages/not-found";
import { PatientsPage } from "@/pages/patients-page";
import { AuthProvider } from "@/providers/auth-provider";
import { RouteProvider } from "@/providers/router-provider";
import { ThemeProvider } from "@/providers/theme-provider";
import { RedirectIfAuthed, RequireAuth } from "@/routes/route-guards";
import "@/styles/globals.css";

createRoot(document.getElementById("root")!).render(
    <StrictMode>
        <ThemeProvider>
            <BrowserRouter>
                <RouteProvider>
                    <AuthProvider>
                        <Routes>
                            <Route
                                path="/login"
                                element={
                                    <RedirectIfAuthed>
                                        <LoginPage />
                                    </RedirectIfAuthed>
                                }
                            />
                            <Route
                                element={
                                    <RequireAuth>
                                        <AdminLayout />
                                    </RequireAuth>
                                }
                            >
                                <Route path="/" element={<Navigate to="/patients" replace />} />
                                <Route path="/patients" element={<PatientsPage />} />
                            </Route>
                            <Route path="*" element={<NotFound />} />
                        </Routes>
                    </AuthProvider>
                </RouteProvider>
            </BrowserRouter>
        </ThemeProvider>
    </StrictMode>,
);
