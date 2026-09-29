
import { useParams } from "react-router-dom"

const ManageUser = () => {

    const { userId } = useParams();

    return (
        <div>
            <h1>Manage User</h1>
            <p>User ID: {userId}</p>
        </div>
    )
}

export default ManageUser;