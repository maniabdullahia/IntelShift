import Button from '../../../components/ui/Button.jsx';
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeadCell } from '../../../components/ui/Table.jsx';
import useUserStore from '../../../store/user.store.js';

import { formatTimeAgo } from '../../../utils/time.js';

import { useNavigate } from 'react-router-dom';

function Users() {


  const navigate = useNavigate();

  const user = useUserStore((state) => state.users);
  // const users = [
  //   {
  //     name: 'Jane Doe',
  //     email: 'jane@acme.com',
  //     workspace: 'Acme Corp',
  //     role: 'Owner',
  //     auth: 'Email / Password',
  //     status: 'Active',
  //     lastLogin: 'Today, 10:42 AM',
  //     action: 'Impersonate',
  //   },
  //   {
  //     name: 'Michael Chen',
  //     email: 'michael@scaleops.io',
  //     workspace: 'ScaleOps',
  //     role: 'Admin',
  //     auth: 'Google SSO',
  //     status: 'Active',
  //     lastLogin: 'Today, 9:18 AM',
  //     action: 'View',
  //   },
  //   {
  //     name: 'Tara Singh',
  //     email: 'tara@launchpilot.com',
  //     workspace: 'LaunchPilot',
  //     role: 'Owner',
  //     auth: 'Email / Password',
  //     status: 'Unverified',
  //     lastLogin: 'Yesterday',
  //     action: 'Resend Verify',
  //   },
  // ];


  const formattedUsers = user.map((user) => ({
    id: user.id,
    name: user.name,
    email: user.email,
    workspace: user.workspace?.name || 'N/A',
    role: user.role || 'Member',
    auth: user.provider ? user.provider : 'Email / Password',
    status: user.accountStatus === 'active' ? 'Active' : user.accountStatus === 'pending' ? 'Unverified' : 'Suspended',
    lastLogin: user.lastLoginAt ? formatTimeAgo(user.lastLoginAt) : 'N/A',
    action: user.action || 'View',
  }));

    console.log("Current formatted user in Users component:", formattedUsers);


  const getRoleBadgeStyles = () => {
    return { background: 'rgba(75, 123, 236, 0.12)', color: 'var(--blue)' };
  };

  const getStatusBadgeStyles = (status) => {
    if (status === 'Active') {
      return { background: 'rgba(38, 222, 129, 0.14)', color: '#16a65c' };
    } else if (status === 'Unverified') {
      return { background: 'rgba(254, 211, 48, 0.18)', color: '#b88b00' };
    } else {
      return { background: 'rgba(255, 92, 92, 0.14)', color: '#ff5c5c' };
    }
  };

  const handleInviteAdmin = () => {
    // Logic to open invite admin modal or navigate to invite page
    console.log('Invite Admin button clicked');
  }

  const handleImpersonate = (user) => {
    // Logic to impersonate the user
    console.log(`Impersonate ${user.name}`);
  }

  const handleView = (userId) => {
    navigate(`/users/${userId}`);
  }

  return (
    <div className="px-10 max-w-375 mx-auto">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6 mb-8">
        <div>
          <h1 className="text-[36px] mb-2 font-bold font-['DM Serif Display'] text-(--primary)">
            Users
          </h1>
          <p className="text-base max-w-195 text-(--text-light)">
            View account owners, admins, members, authentication state, and support access controls.
          </p>
        </div>
        <div className="flex items-center">
          <Button title="Invite Admin" variant="secondary" onClick={handleInviteAdmin} />
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-lg overflow-hidden border border-(--border) mb-8">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeadCell>User</TableHeadCell>
              <TableHeadCell>Workspace</TableHeadCell>
              <TableHeadCell>Role</TableHeadCell>
              <TableHeadCell>Auth</TableHeadCell>
              <TableHeadCell>Status</TableHeadCell>
              <TableHeadCell>Last Login</TableHeadCell>
              <TableHeadCell>Support</TableHeadCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {formattedUsers.map((user, index) => (
              <TableRow key={index}>
                <TableCell className="py-4.5 px-5">
                  <div className="font-bold text-(--text)">{user.name}</div>
                  <div className="text-sm mt-1 text-(--text-light)">{user.email}</div>
                </TableCell>
                <TableCell className="text-[14px] align-middle py-4.5 px-5 text-(--text)">
                  {user.workspace}
                </TableCell>
                <TableCell className="py-4.5 px-5">
                  <span className="inline-block px-2 py-1 rounded-sm text-xs font-semibold" style={{ ...getRoleBadgeStyles() }}>
                    {user.role}
                  </span>
                </TableCell>
                <TableCell className="text-[14px] align-middle py-4.5 px-5 text-(--text)">
                  {user.auth}
                </TableCell>
                <TableCell className="py-4.5 px-5">
                  <span className="inline-block px-2 py-1 rounded-sm text-xs font-semibold" style={{ ...getStatusBadgeStyles(user.status) }}>
                    {user.status}
                  </span>
                </TableCell>
                <TableCell className="text-[14px] align-middle py-4.5 px-5 text-(--text-light)">
                  {user.lastLogin}
                </TableCell>
                <TableCell className="py-4.5 px-5">
                  <Button title={user.action} variant="ghost" onClick={() => handleView(user.id)} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export default Users;
