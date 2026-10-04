export function statusColor(status) {
    if (status.includes("SUCCESS")) return "#34d399";
    if (status.includes("Already") || status.includes("Hold")) return "#fb923c";
    if (status.includes("Timeout") || status.includes("Failed")) return "#ef4444";
    return "#38bdf8";
}
