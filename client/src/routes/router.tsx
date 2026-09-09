import { createBrowserRouter, type RouteObject } from "react-router-dom";
import { AdminGuard } from "@/components/layout/AdminGuard";
import { AppLayout } from "@/components/layout/AppLayout";
import { AuthGuard } from "@/components/layout/AuthGuard";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { AdminChunksPage } from "@/features/admin";
import {
  ForgotPasswordPage,
  LoginPage,
  ResetPasswordPage,
  SignupPage,
} from "@/features/auth";
import { ProjectsPage } from "@/features/projects";
import { SettingsPage } from "@/features/settings";
import { CookiesPage } from "@/pages/CookiesPage";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PricingPage } from "@/pages/PricingPage";
import { PrivacyPage } from "@/pages/PrivacyPage";
import { ProjectWorkspacePage } from "@/pages/ProjectWorkspacePage";
import { RouteErrorPage } from "@/pages/RouteErrorPage";
import { TermsPage } from "@/pages/TermsPage";
import { TutorialPage } from "@/pages/TutorialPage";
import { SessionProvider } from "@/providers/SessionProvider";

export const routes: RouteObject[] = [
  {
    errorElement: <RouteErrorPage />,
    children: [
      {
        path: "/",
        element: (
          <PublicLayout>
            <HomePage />
          </PublicLayout>
        ),
      },
      {
        path: "/login",
        element: (
          <PublicLayout>
            <LoginPage />
          </PublicLayout>
        ),
      },
      {
        path: "/signup",
        element: (
          <PublicLayout>
            <SignupPage />
          </PublicLayout>
        ),
      },
      {
        path: "/forgot-password",
        element: (
          <PublicLayout>
            <ForgotPasswordPage />
          </PublicLayout>
        ),
      },
      {
        path: "/privacy",
        element: (
          <PublicLayout>
            <PrivacyPage />
          </PublicLayout>
        ),
      },
      {
        path: "/terms",
        element: (
          <PublicLayout>
            <TermsPage />
          </PublicLayout>
        ),
      },
      {
        path: "/cookies",
        element: (
          <PublicLayout>
            <CookiesPage />
          </PublicLayout>
        ),
      },
      {
        path: "/reset-password",
        element: (
          <PublicLayout>
            <ResetPasswordPage />
          </PublicLayout>
        ),
      },
      {
        element: (
          <SessionProvider>
            <AuthGuard />
          </SessionProvider>
        ),
        children: [
          {
            element: <AppLayout />,
            children: [
              {
                path: "/projects",
                element: <ProjectsPage />,
              },
              {
                path: "/projects/:projectId",
                element: <ProjectWorkspacePage />,
              },
              {
                path: "/settings",
                element: <SettingsPage />,
              },
              {
                path: "/abonnement",
                element: <PricingPage />,
              },
              {
                path: "/tutoriel",
                element: <TutorialPage />,
              },
              {
                element: <AdminGuard />,
                children: [
                  {
                    path: "/admin/chunks",
                    element: <AdminChunksPage />,
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
