import type { ResearchDriveService, Project, Member, Role } from "./project";

export function getDrive(): ResearchDriveService {
    return {
        name: "reslig-202200001-Tītoki-metabolomics",
        allocated_gb: 25600.0
    };
}

export function getProject(): Project {
    return {
        title: "Tītoki metabolomics",
        description: "Stress in plants could be defined as any change in growth condition(s) that disrupts metabolic homeostasis and requires an adjustment of metabolic pathways in a process that is usually referred to as acclimation. Metabolomics could contribute significantly to the study of stress biology in plants and other organisms by identifying different compounds, such as by-products of stress metabolism, stress signal transduction molecules or molecules that are part of the acclimation response of plants.",
        division: "Liggins Institute",
        members: [
            {
                person: {
                    full_name: "Samina Nicholas",
                    email: "s.nicholas@test.auckland.ac.nz",
                    username: "snic021"
                },
                roles: [{
                    name: "Project Owner"
                }]
            },
            {
                person: {
                    full_name: "Zach Luther",
                    email: "z.luther@test.auckland.ac.nz",
                    username: "zlut014"
                },
                roles: [{
                    name: "Project Team Member"
                }]
            },
            {
                person: {
                    full_name: "Jarrod Hossam",
                    email: "j.hossam@test.auckland.ac.nz",
                    username: "jhos225"
                },
                roles: [{
                    name: "Project Team Member"
                }]
            },
            {
                person: {
                    full_name: "Melisa Edric",
                    email: "m.edric@test.auckland.ac.nz",
                    username: "medr894"
                },
                roles: [{
                    name: "Project Team Member"
                }]
            }
        ]
    };
}
/**
 * Given a list of members, filter for project owners.
 * @param members List of members to search through
 * @returns Members who are project owners.
 */
export function getProjectOwners(members: Member[]): Member[] {
    return members.filter(member =>
        member.roles.some(
            (role: Role) => role.name === "Project Owner"
        )
    );
}

/**
 * Given a list of project members, filter for ordinary members.
 * @param members List of members to search through
 * @returns Members who are not project owners.
 */
export function getProjectMembers(members: Member[]): Member[] {
    return members.filter(member =>
        !member.roles.some(
            (role: Role) => role.name === "Project Owner"
        )
    );
}