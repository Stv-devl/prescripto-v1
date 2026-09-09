import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";

interface WrapperProps {
  children: ReactNode;
}

/**
 * @param gcTime - Raise it to Infinity when a case seeds the cache: at 0 an
 * entry is collected the moment it loses its observer, so the seed vanishes.
 */
function createTestQueryClient(gcTime = 0): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

interface CustomRenderOptions extends Omit<RenderOptions, "wrapper"> {
  route?: string;
  queryClient?: QueryClient;
}

function AllProviders({
  children,
  queryClient,
}: WrapperProps & { queryClient: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

export function renderWithProviders(
  ui: ReactElement,
  options: CustomRenderOptions = {},
) {
  const { queryClient = createTestQueryClient(), ...renderOptions } = options;

  return {
    ...render(ui, {
      wrapper: ({ children }) => (
        <AllProviders queryClient={queryClient}>{children}</AllProviders>
      ),
      ...renderOptions,
    }),
    queryClient,
  };
}

export function createQueryClientWrapper(client?: QueryClient) {
  const queryClient = client ?? createTestQueryClient();
  return {
    wrapper: ({ children }: WrapperProps) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
    queryClient,
  };
}

export { createTestQueryClient };
