/**
 * Functions for loading information about the archive request.
 */
import { requestInfo } from "@/store";
import { getDriveInfoApiV1ResdriveinfoGet } from "./sdk.gen";
import type { ProjectWithDriveMember, ResearchDriveService } from "./types.gen";

/**
 * Retrieves project information based on project code in URL.
 * @returns Project information from server.
 * @throws Exception if server did not return data or received an error status code.
 */
async function getProject(): Promise<ProjectWithDriveMember> {
    const params = new URLSearchParams(window.location.search);
    const driveId = params.get("drive");
    if (driveId === null) {
        throw new Error("No drive name found in parameter.");
    }
    const response = await getDriveInfoApiV1ResdriveinfoGet({
        query: {
            drive_id: driveId
        }
    });
    if (response.error || !response.response.ok || response.data === undefined) {
        throw response.error;
    }
    return response.data;
}

/**
 * Retrieves drive information from server.
 * @returns Drive information from server.
 * @throws Exception if server did not return data.
 */
async function getDrive(): Promise<ResearchDriveService> {
    const project = await getProject();
    if (!project) {
        throw new Error("Project is not loaded.");
    }
    return project.research_drives[0];
}

/**
 * Retrieves archive information from server and stores it in the requestInfo store.
* @returns True if request was loaded successfully, false if not.
 */
export async function loadRequestInfo(): Promise<boolean> {
    // Pre-populate archive request info.
    try {
        requestInfo.isLoading = true;
        requestInfo.project = await getProject();
        requestInfo.drive = await getDrive();
        requestInfo.isLoading = false;
        return true;
    } catch (e) {
        requestInfo.isLoading = false;
        requestInfo.error = e;
        console.error("Could not retrieve request information. Bad invite link?");
        console.error(e);
        return false;
    }
}