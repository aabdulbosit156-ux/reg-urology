export type InvitableRole = "director" | "admin" | "analyst";

export interface StaffSessionCreateResponse {
    token: string;
    role: InvitableRole;
    deep_link: string;
    expires_at: string;
}
