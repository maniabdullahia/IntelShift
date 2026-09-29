
import useScrollReveal from './hooks/useScrollReveal';



import router from './router';
import { RouterProvider } from 'react-router';

function App() {

  useScrollReveal();

  return (
    <RouterProvider router={router} />
  )
}

export default App
