import { createApp } from "vue";
import "@fontsource-variable/golos-text";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/layout.css";
import "./styles/features/debates.css";
import "./styles/features/debate-analysis.css";
import App from "./App.vue";
import { initializeSession } from "./auth/session";
import { makeRouter } from "./router";

await initializeSession();
const router = makeRouter();
const app = createApp(App);
app.use(router);
await router.isReady();
app.mount("#app");
