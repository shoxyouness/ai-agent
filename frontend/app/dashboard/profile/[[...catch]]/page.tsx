import { UserProfile } from '@clerk/nextjs'
import React from 'react'

const ProfilePage = () => {
  return (
    <div className=' flex items-center justify-center'>
      <UserProfile />
    </div>
  )
}

export default ProfilePage