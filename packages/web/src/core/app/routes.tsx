import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from './AppShell';
import { DispatchPage } from '../../domains/dispatch/pages/DispatchPage';
import { TrafficPage } from '../../domains/traffic/pages/TrafficPage';

export const appRouter = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <Navigate to="/traffic" replace />,
      },
      {
        path: 'traffic',
        element: <TrafficPage />,
      },
      {
        path: 'dispatch',
        element: <DispatchPage />,
      },
      {
        path: '*',
        element: <Navigate to="/traffic" replace />,
      },
    ],
  },
]);
