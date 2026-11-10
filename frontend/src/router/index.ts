import { createRouter, createWebHistory } from "vue-router";
import { useSession } from "../auth/session";
import { useProfile } from "../features/profile/useProfile";
import DashboardPage from "../pages/DashboardPage.vue";
import NewDebatePage from "../pages/NewDebatePage.vue";
import DebatePage from "../pages/DebatePage.vue";
import WelcomePage from "../pages/WelcomePage.vue";
import ProfilePage from "../pages/ProfilePage.vue";

export function makeRouter() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: "/", name: "welcome", component: WelcomePage },
      { path: "/auth/callback", redirect: "/debates" },
      {
        path: "/debates",
        name: "debates",
        component: DashboardPage,
        meta: { authenticated: true },
      },
      {
        path: "/debates/new",
        component: NewDebatePage,
        meta: { authenticated: true },
      },
      {
        path: "/debates/:id/chats/:chatId?",
        component: DebatePage,
        meta: { authenticated: true },
      },
      {
        path: "/debates/:id",
        component: DebatePage,
        meta: { authenticated: true },
      },
      {
        path: "/onboarding",
        name: "onboarding",
        component: ProfilePage,
        props: { onboarding: true },
        meta: { authenticated: true },
      },
      {
        path: "/profile",
        name: "profile",
        component: ProfilePage,
        meta: { authenticated: true },
      },
      { path: "/:pathMatch(.*)*", redirect: "/" },
    ],
  });
  router.beforeEach(async (to) => {
    const { authenticated } = useSession();
    if (!authenticated.value)
      return to.meta.authenticated ? { name: "welcome" } : true;
    const state = useProfile();
    if (!state.profile.value) await state.load();
    if (!state.profile.value)
      return to.name === "profile" ? true : { name: "profile" };
    if (!state.profile.value.onboardingCompleted)
      return to.name === "onboarding" ? true : { name: "onboarding" };
    return to.name === "welcome" || to.name === "onboarding"
      ? { name: "debates" }
      : true;
  });
  return router;
}
