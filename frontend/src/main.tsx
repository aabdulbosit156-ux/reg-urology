import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { AdminLayout } from "@/components/layout/admin-layout";
import { ActivityPage } from "@/pages/activity-page";
import { CalendarPage } from "@/pages/calendar-page";
import { DashboardPage } from "@/pages/dashboard-page";
import { LoginPage } from "@/pages/login-page";
import { NotFound } from "@/pages/not-found";
import { PatientsPage } from "@/pages/patients-page";
import { SettingsPage } from "@/pages/settings-page";
import { StaffPage } from "@/pages/staff-page";
import { AuthProvider } from "@/providers/auth-provider";
import { RouteProvider } from "@/providers/router-provider";
import { ThemeProvider } from "@/providers/theme-provider";
import { RedirectIfAuthed, RequireAuth, RequireRole } from "@/routes/route-guards";
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
                                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                                <Route path="/dashboard" element={<DashboardPage />} />
                                <Route path="/patients" element={<PatientsPage />} />
                                <Route
                                    path="/calendar"
                                    element={
                                        <RequireRole roles={["dev", "director", "admin"]}>
                                            <CalendarPage />
                                        </RequireRole>
                                    }
                                />
                                <Route
                                    path="/staff"
                                    element={
                                        <RequireRole roles={["dev", "director", "admin"]}>
                                            <StaffPage />
                                        </RequireRole>
                                    }
                                />
                                <Route
                                    path="/activity"
                                    element={
                                        <RequireRole roles={["dev", "director"]}>
                                            <ActivityPage />
                                        </RequireRole>
                                    }
                                />
                                <Route
                                    path="/settings"
                                    element={
                                        <RequireRole roles={["dev", "director"]}>
                                            <SettingsPage />
                                        </RequireRole>
                                    }
                                />
                            </Route>
                            <Route path="*" element={<NotFound />} />
                        </Routes>
                    </AuthProvider>
                </RouteProvider>
            </BrowserRouter>
        </ThemeProvider>
    </StrictMode>,
);
