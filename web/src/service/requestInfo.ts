/**
 * Functions for loading information about the archive request.
 */
import { requestInfo } from "@/store";
import { getDriveInfoApiV1DriveinfoGet } from "../client/sdk.gen";
import type { DriveInfoResponse } from "../client/types.gen";

/**
 * Fetches drive and project info from the API using the drive name from the URL.
 * @returns Combined drive and project info.
 * @throws Exception if server did not return data or received an error status code.
 */
async function getDriveInfo(): Promise<DriveInfoResponse> {
  const params = new URLSearchParams(window.location.search);
  const driveName = params.get("drive");
  if (driveName === null) {
    throw new Error("No drive name found in parameter.");
  }
  const response = await getDriveInfoApiV1DriveinfoGet({
    query: {
      drive_name: driveName
    }
  });
  if (response.error || !response.response.ok || response.data === undefined) {
    throw response.error;
  }
  return response.data;
}

/**
 * Retrieves archive information from server and stores it in the requestInfo store.
 * @returns True if request was loaded successfully, false if not.
 */
export async function loadRequestInfo(): Promise<boolean> {
  try {
    requestInfo.isLoading = true;
    const driveInfo = await getDriveInfo();
    requestInfo.project = driveInfo.project;
    requestInfo.drive = driveInfo.drive;
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
