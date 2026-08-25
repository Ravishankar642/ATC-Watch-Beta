import { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";
import { disableNotifications, enableNotifications, isAndroid, isIos, isStandalonePwa, pushSupported } from "../services/push";
import type { UserSettings } from "../types/api";
import "./SettingsScreen.css";

export default function SettingsScreen() {
  const { me, refresh } = useAuth();
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [notifStatus, setNotifStatus] = useState<"idle" | "granted" | "denied" | "unsupported">("idle");
  const [testSent, setTestSent] = useState(false);
  const [callsignInput, setCallsignInput] = useState("");
  const [callsignSaved, setCallsignSaved] = useState(false);
  const [notifError, setNotifError] = useState<string | null>(null);
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    api.getSettings().then((s) => {
      setSettings(s);
      setCallsignInput(s.tracked_callsign ?? "");
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      setInstallPrompt(event as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    return () => window.removeEventListener("beforeinstallprompt", onBeforeInstall);
  }, []);

  const updateSetting = async (patch: Partial<UserSettings>) => {
    if (!settings) return;
    const optimistic = { ...settings, ...patch };
    setSettings(optimistic);
    const saved = await api.updateSettings(patch);
    setSettings(saved);
  };

  const handleTrackCallsign = async () => {
    const trimmed = callsignInput.trim().toUpperCase();
    await updateSetting({ tracked_callsign: trimmed || null });
    setCallsignSaved(true);
    setTimeout(() => setCallsignSaved(false), 2000);
  };

  const handleTrackOwnFlight = async () => {
    setCallsignInput("");
    await updateSetting({ tracked_callsign: null });
  };

  const handleEnableNotifications = async () => {
    setNotifError(null);
    try {
      const result = await enableNotifications();
      setNotifStatus(result);
      if (result === "granted") {
        const saved = await api.getSettings();
        setSettings(saved);
      } else if (result === "unsupported") {
        setNotifError("Push isn't supported in this browser/context.");
      } else if (result === "denied") {
        setNotifError("iOS denied the notification permission request.");
      }
    } catch (err) {
      console.error("enableNotifications failed:", err);
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes("503") || message.toLowerCase().includes("vapid")) {
        setNotifError("The server isn't configured for push yet (missing VAPID keys). This is a deployment setting, not something fixable from the app — see the README's Push Notifications setup section.");
      } else {
        setNotifError(message);
      }
    }
  };

  const handleDisableNotifications = async () => {
    await disableNotifications();
    const saved = await api.getSettings();
    setSettings(saved);
  };

  const handleTestPush = async () => {
    setNotifError(null);
    try {
      await api.sendTestPush();
      setTestSent(true);
      setTimeout(() => setTestSent(false), 3000);
    } catch (err) {
      console.error("sendTestPush failed:", err);
      setNotifError(err instanceof Error ? err.message : String(err));
    }
  };

  const showInstallInstructions = isIos() && !isStandalonePwa();
  const showAndroidInstall = isAndroid() && !isStandalonePwa();

  const handleAndroidInstall = async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    setInstallPrompt(null);
  };

  return (
    <div className="screen">
      <header className="screen__header">
        <h1>Settings</h1>
      </header>

      {me && (
        <div className="account-row">
          <span className="dim">VATSIM CID</span>
          <span className="mono">{me.vatsim_cid}</span>
        </div>
      )}

      <section className="settings-card">
        <h2>Tracked Flight</h2>
        <p className="dim">
          Enter any callsign on the network to track it — your own flight, a friend's, or anyone else currently
          online. Leave it empty to automatically track your own VATSIM login.
        </p>
        <div className="callsign-row">
          <input
            className="callsign-input mono"
            type="text"
            placeholder="e.g. UAL123"
            value={callsignInput}
            onChange={(e) => setCallsignInput(e.target.value.toUpperCase())}
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            maxLength={12}
          />
          <button className="btn btn--primary" onClick={handleTrackCallsign}>
            {callsignSaved ? "Saved!" : "Track"}
          </button>
        </div>
        {settings?.tracked_callsign && (
          <div className="tracked-row">
            <span className="status-dot status-dot--online" />
            <span>
              Currently tracking <strong className="mono">{settings.tracked_callsign}</strong>
            </span>
            <button className="link-btn" onClick={handleTrackOwnFlight}>
              Reset to my own flight
            </button>
          </div>
        )}
      </section>

      {showInstallInstructions && (
        <section className="settings-card">
          <h2>Install to Home Screen</h2>
          <p className="dim">
            Notifications only work once this app is installed. In Safari, tap the Share icon, then
            "Add to Home Screen." Open the app from your Home Screen icon afterward.
          </p>
          <ol className="install-steps">
            <li>Tap <strong>Share</strong> in Safari's toolbar</li>
            <li>Tap <strong>Add to Home Screen</strong></li>
            <li>Open <strong>ATC Watch Beta</strong> from your Home Screen</li>
          </ol>
        </section>
      )}

      {showAndroidInstall && (
        <section className="settings-card">
          <h2>Install on Android</h2>
          <p className="dim">Install ATC Watch Beta for a full-screen map, faster launch, and reliable alerts.</p>
          {installPrompt ? (
            <button className="btn btn--primary" onClick={handleAndroidInstall}>Install app</button>
          ) : (
            <p className="dim">Open Chrome’s menu and choose <strong>Install app</strong> or <strong>Add to Home screen</strong>.</p>
          )}
        </section>
      )}

      <section className="settings-card">
        <h2>Notifications</h2>
        {!pushSupported() && <p className="dim">Push notifications aren't supported in this browser.</p>}
        {pushSupported() && !settings?.notifications_enabled && (
          <>
            <p className="dim">Get alerted when ATC comes online ahead of your route — even when the app is closed.</p>
            <button className="btn btn--primary" onClick={handleEnableNotifications}>
              Enable Notifications
            </button>
            {notifStatus === "denied" && (
              <p className="warn-text">Permission denied. Re-enable notifications for this app in your device settings.</p>
            )}
          </>
        )}
        {settings?.notifications_enabled && (
          <>
            <div className="toggle-row">
              <span className="status-dot status-dot--online" />
              <span>Notifications enabled</span>
            </div>
            <div className="settings-card__actions">
              <button className="btn" onClick={handleTestPush}>
                {testSent ? "Sent!" : "Send test notification"}
              </button>
              <button className="btn btn--danger" onClick={handleDisableNotifications}>
                Disable
              </button>
            </div>
          </>
        )}
        {notifError && <p className="warn-text">Error: {notifError}</p>}
      </section>

      {settings && (
        <section className="settings-card">
          <h2>Alert Thresholds</h2>

          <SliderRow
            label="Notify before ATC"
            value={settings.notify_minutes_before}
            unit="min"
            min={2}
            max={60}
            step={1}
            onChange={(v) => updateSetting({ notify_minutes_before: v })}
          />
          <SliderRow
            label="Notify before ATC"
            value={settings.notify_nm_before}
            unit="NM"
            min={10}
            max={300}
            step={10}
            onChange={(v) => updateSetting({ notify_nm_before: v })}
          />

          <ToggleRow
            label="Entry alerts"
            description="Notify when entering relevant ATC airspace"
            checked={settings.entry_alerts_enabled}
            onChange={(v) => updateSetting({ entry_alerts_enabled: v })}
          />
          <ToggleRow
            label="Controller-change alerts"
            description="Notify when a new controller takes over coverage"
            checked={settings.controller_change_alerts_enabled}
            onChange={(v) => updateSetting({ controller_change_alerts_enabled: v })}
          />
          <ToggleRow
            label="Offline alerts"
            description="Notify when a relevant controller goes offline"
            checked={settings.offline_alerts_enabled}
            onChange={(v) => updateSetting({ offline_alerts_enabled: v })}
          />
        </section>
      )}

      {settings && (
        <section className="settings-card">
          <h2>Traffic Filters</h2>
          <SliderRow
            label="Traffic radius"
            value={settings.traffic_radius_nm}
            unit="NM"
            min={25}
            max={1000}
            step={25}
            onChange={(v) => updateSetting({ traffic_radius_nm: v })}
          />
          <SliderRow
            label="Altitude filter"
            value={settings.altitude_filter_ft}
            unit="ft"
            min={1000}
            max={60000}
            step={1000}
            onChange={(v) => updateSetting({ altitude_filter_ft: v })}
          />
        </section>
      )}

      <button className="btn btn--ghost" onClick={() => api.logout().then(refresh)}>
        Log out
      </button>
    </div>
  );
}

function SliderRow({
  label, value, unit, min, max, step, onChange,
}: { label: string; value: number; unit: string; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <div className="slider-row">
      <div className="slider-row__top">
        <span>{label}</span>
        <span className="mono amber-glow">{value.toLocaleString()} {unit}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function ToggleRow({
  label, description, checked, onChange,
}: { label: string; description: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="toggle-row-full">
      <div>
        <div>{label}</div>
        <div className="dim toggle-row-full__desc">{description}</div>
      </div>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}
