import useAuthStore from "../../../store/auth.store";

const UserLoader = async () => {
    const { syncUser } = useAuthStore.getState();
    
    return await syncUser();
};

export default UserLoader;