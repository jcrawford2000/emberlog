import { RouterProvider } from 'react-router-dom';
import { appRouter } from './core/app/routes';

export default function App() {
  return <RouterProvider router={appRouter} />;
}
