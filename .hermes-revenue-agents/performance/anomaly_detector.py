"""
AnomalyDetector — Detects suspicious patterns in agent activity.
Part of the V5 Hermes Revenue Agent Network.
"""
from datetime import datetime


# Thresholds (all configurable)
_DEFAULTS = {
    "revenue_spike_pct": 300.0,        # % increase from baseline
    "qa_pass_rate_drop_pct": 50.0,     # % drop from baseline
    "qa_pass_rate_spike_pct": 200.0,   # % increase from baseline (suspicious)
    "task_volume_increase_pct": 400.0, # % increase from baseline
    "log_gap_minutes": 120.0,          # gap longer than this in minutes
    "tx_hash_reuse_threshold": 2,      # reuse count
    "wallet_change_interval_days": 7,  # too-frequent changes
    "ip_leak_threshold": 3,            # IPs per day
    "complaint_threshold": 5,          # complaints per period
}


class AnomalyDetector:
    """Analyses recent activity of an agent and returns detected anomalies.

    Each anomaly is a dict:
        {
            "type": str,
            "severity": "low" | "medium" | "high" | "critical",
            "evidence": str,
            "recommended_action": str,
        }
    """

    def __init__(self, thresholds: dict = None):
        self.thresholds = {**_DEFAULTS, **(thresholds or {})}

    def detect(self, agent_id: str, recent_activity: dict) -> list:
        """Run all anomaly detection checks on the given activity data.

        Parameters
        ----------
        agent_id : str
        recent_activity : dict
            Expected keys (all optional):
                - revenue_baseline, current_revenue
                - qa_pass_rate_baseline, current_qa_pass_rate
                - task_volume_baseline, current_task_volume
                - log_timestamps: list of ISO timestamp strings
                - tx_hashes: list of transaction hashes
                - wallet_addresses: list of wallet change events
                - ip_addresses: list of IP event dicts
                - complaints: list of complaint dicts or int count

        Returns
        -------
        list[dict]  — each dict as described above.
        """
        anomalies = []

        # ── 1. Sudden revenue spike ─────────────────────────────── #
        spike = self._check_revenue_spike(recent_activity)
        if spike:
            anomalies.append(spike)

        # ── 2. Sudden QA pass rate change (drop or spike) ───────── #
        qa_change = self._check_qa_change(recent_activity)
        if qa_change:
            anomalies.append(qa_change)

        # ── 3. Abnormal task volume increase ────────────────────── #
        vol = self._check_task_volume(recent_activity)
        if vol:
            anomalies.append(vol)

        # ── 4. Log gaps ─────────────────────────────────────────── #
        gaps = self._check_log_gaps(recent_activity)
        anomalies.extend(gaps)

        # ── 5. TX hash reuse pattern ────────────────────────────── #
        tx_anomaly = self._check_tx_reuse(recent_activity)
        if tx_anomaly:
            anomalies.append(tx_anomaly)

        # ── 6. Wallet address change frequency ──────────────────── #
        wallet_anomaly = self._check_wallet_changes(recent_activity)
        if wallet_anomaly:
            anomalies.append(wallet_anomaly)

        # ── 7. IP leak increase ─────────────────────────────────── #
        ip_anomaly = self._check_ip_leaks(recent_activity)
        if ip_anomaly:
            anomalies.append(ip_anomaly)

        # ── 8. Complaint increase ───────────────────────────────── #
        complaint_anomaly = self._check_complaints(recent_activity)
        if complaint_anomaly:
            anomalies.append(complaint_anomaly)

        return anomalies

    # ═══════════════════════════════════════════════════════════════ #
    # Individual checks
    # ═══════════════════════════════════════════════════════════════ #

    def _check_revenue_spike(self, act: dict) -> dict | None:
        baseline = act.get("revenue_baseline", 0.0)
        current = act.get("current_revenue", act.get("revenue", 0.0))
        if baseline <= 0:
            return None
        pct = ((current - baseline) / baseline) * 100.0
        if pct > self.thresholds["revenue_spike_pct"]:
            return {
                "type": "sudden_revenue_spike",
                "severity": "high",
                "evidence": (
                    f"Revenue spike of {pct:.1f}% above baseline "
                    f"({current:.2f} vs {baseline:.2f})"
                ),
                "recommended_action": "Investigate revenue source; verify on-chain tx.",
            }
        return None

    def _check_qa_change(self, act: dict) -> dict | None:
        baseline = act.get("qa_pass_rate_baseline", None)
        current = act.get("current_qa_pass_rate", act.get("qa_pass_rate", None))
        if baseline is None or current is None or baseline <= 0:
            return None
        pct = ((current - baseline) / baseline) * 100.0

        # Suspiciously high increase
        if pct > self.thresholds["qa_pass_rate_spike_pct"]:
            return {
                "type": "sudden_qa_pass_rate_spike",
                "severity": "high",
                "evidence": (
                    f"QA pass rate increased {pct:.1f}% above baseline "
                    f"({current:.1f}% vs {baseline:.1f}%)"
                ),
                "recommended_action": "Audit QA process; check for tampering.",
            }
        # Suspicious drop
        if pct < -self.thresholds["qa_pass_rate_drop_pct"]:
            return {
                "type": "sudden_qa_pass_rate_drop",
                "severity": "medium",
                "evidence": (
                    f"QA pass rate dropped {abs(pct):.1f}% below baseline "
                    f"({current:.1f}% vs {baseline:.1f}%)"
                ),
                "recommended_action": "Review agent performance; provide retraining.",
            }
        return None

    def _check_task_volume(self, act: dict) -> dict | None:
        baseline = act.get("task_volume_baseline", 0)
        current = act.get("current_task_volume", act.get("task_volume", 0))
        if baseline <= 0:
            return None
        pct = ((current - baseline) / baseline) * 100.0
        if pct > self.thresholds["task_volume_increase_pct"]:
            return {
                "type": "abnormal_task_volume_increase",
                "severity": "medium",
                "evidence": (
                    f"Task volume increased {pct:.1f}% above baseline "
                    f"({current} vs {baseline})"
                ),
                "recommended_action": "Check for automated/scripted task submission.",
            }
        return None

    def _check_log_gaps(self, act: dict) -> list:
        timestamps = act.get("log_timestamps", [])
        if len(timestamps) < 2:
            return []
        gaps = []
        parsed = []
        for ts in timestamps:
            try:
                parsed.append(datetime.fromisoformat(ts))
            except (ValueError, TypeError):
                continue
        parsed.sort()
        threshold_min = self.thresholds["log_gap_minutes"]
        for i in range(1, len(parsed)):
            gap = (parsed[i] - parsed[i - 1]).total_seconds() / 60.0
            if gap > threshold_min:
                severity = "high" if gap > threshold_min * 3 else "medium"
                gaps.append({
                    "type": "log_gap",
                    "severity": severity,
                    "evidence": (
                        f"Log gap of {gap:.1f} minutes between "
                        f"{parsed[i-1].isoformat()} and {parsed[i].isoformat()}"
                    ),
                    "recommended_action": "Check agent uptime; verify no unauthorised downtime.",
                })
        return gaps

    def _check_tx_reuse(self, act: dict) -> dict | None:
        tx_hashes = act.get("tx_hashes", [])
        if not tx_hashes:
            return None
        from collections import Counter
        counts = Counter(tx_hashes)
        most_common = counts.most_common(1)
        if most_common and most_common[0][1] >= self.thresholds["tx_hash_reuse_threshold"]:
            h, cnt = most_common[0]
            return {
                "type": "tx_hash_reuse_pattern",
                "severity": "critical",
                "evidence": (
                    f"Transaction hash {h[:16]}... reused {cnt} times "
                    f"(threshold: {self.thresholds['tx_hash_reuse_threshold']})"
                ),
                "recommended_action": "Immediate fraud investigation — tx reuse indicates fabrication.",
            }
        return None

    def _check_wallet_changes(self, act: dict) -> dict | None:
        wallets = act.get("wallet_addresses", [])
        if not wallets:
            return None
        timestamps = []
        for w in wallets:
            if isinstance(w, str):
                timestamps.append(w)
            elif isinstance(w, dict):
                timestamps.append(w.get("timestamp", w.get("date", "")))
        # Heuristic: count distinct wallet change events in last N days
        # We look for >1 change within the configured interval
        try:
            parsed = sorted(datetime.fromisoformat(t) for t in timestamps if t)
        except (ValueError, TypeError):
            parsed = []
        if len(parsed) < 2:
            return None
        interval_days = self.thresholds["wallet_change_interval_days"]
        min_gap = min(
            (parsed[i] - parsed[i - 1]).days for i in range(1, len(parsed))
        )
        if min_gap < interval_days:
            return {
                "type": "wallet_address_change",
                "severity": "high",
                "evidence": (
                    f"Wallet changed {len(parsed)} times with minimum "
                    f"gap of {min_gap} days (interval threshold: {interval_days}d)"
                ),
                "recommended_action": "Flag wallet for review; verify ownership chain.",
            }
        return None

    def _check_ip_leaks(self, act: dict) -> dict | None:
        ips = act.get("ip_addresses", [])
        if not ips:
            return None
        unique_ips = set()
        for ip in ips:
            if isinstance(ip, str):
                unique_ips.add(ip)
            elif isinstance(ip, dict):
                unique_ips.add(ip.get("ip", ""))
        if len(unique_ips) > self.thresholds["ip_leak_threshold"]:
            return {
                "type": "ip_leak_increase",
                "severity": "medium",
                "evidence": (
                    f"Detected {len(unique_ips)} unique IP addresses "
                    f"(threshold: {self.thresholds['ip_leak_threshold']})"
                ),
                "recommended_action": "Investigate IP distribution; check for credential sharing.",
            }
        return None

    def _check_complaints(self, act: dict) -> dict | None:
        complaints = act.get("complaints", [])
        if isinstance(complaints, (int, float)):
            count = int(complaints)
        else:
            count = len(complaints)
        if count > self.thresholds["complaint_threshold"]:
            return {
                "type": "complaint_increase",
                "severity": "high",
                "evidence": (
                    f"Received {count} complaints "
                    f"(threshold: {self.thresholds['complaint_threshold']})"
                ),
                "recommended_action": "Review complaint details; suspend if pattern persists.",
            }
        return None
