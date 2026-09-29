import React from 'react'

function Footer() {
  return (
    <footer className="bg-white border-t border-gray-200 mt-auto">
      <div className="container mx-auto py-4 text-center text-sm text-gray-600">
        &copy; {new Date().getFullYear()} Intelshift AI. All rights reserved.
      </div>
    </footer>
  )
}

export default Footer
