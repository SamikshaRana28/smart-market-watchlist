// // import react from '@vitejs/plugin-react'
// // import tailwindcss from '@tailwindcss/vite'
// // import { defineConfig } from 'vite'

// // export default defineConfig({
// //   plugins: [react(), tailwindcss()],
// //   server: {
// //     port: 5173,
// //     proxy: {
// //       '/watchlists': 'http://127.0.0.1:8000',
// //       '/market': 'http://127.0.0.1:8000',
// //       '/health': 'http://127.0.0.1:8000',
// //     },
// //   },
// // })


// import { defineConfig } from 'vite'
// import react from '@vitejs/plugin-react'
// import tailwindcss from '@tailwindcss/vite'

// export default defineConfig({
//   plugins: [react(), tailwindcss()],
// })

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/watchlists': 'http://127.0.0.1:8000',
      '/market': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})