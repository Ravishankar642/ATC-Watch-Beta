import { api } from "../services/api";
import "./LoginScreen.css";

export default function LoginScreen() {
  return (
    <div className="login-screen">
      <div className="login-screen__badge mono amber-glow">ATC WATCH</div>
      <h1>ATC Watch Beta</h1>
      <p className="dim">
        Live traffic, filed-route ATC prediction, and push alerts for your VATSIM flights — right on your
        iPhone's Home Screen.
      </p>
      <a className="btn btn--primary login-screen__cta" href={api.loginUrl()}>
        Connect with VATSIM
      </a>
      <p className="login-screen__note dim">
        Uses VATSIM Connect OAuth — your VATSIM password is never seen by this app.
      </p>
    </div>
  );
}
