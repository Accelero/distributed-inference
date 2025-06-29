# Distributed Inference Architecture

Submission for Distributed AI Engineer - Coding Challenge.

## Future Improvements & Roadmap

- Implement dynamic scaling of worker instances based on system load
- Replace custom client-side load balancing with an L7 load balancer such as NGINX or Envoy Proxy
- Migrate to Kubernetes for automated scaling, load balancing, and health probing
- Add container ID to heartbeat response, so the coordinator knows. NOTICE: Handle cases where the ID is not known before the first heartbeat.

---

**Third-Party Licenses:**

This project includes third-party software components. For details, see the [Third-Party Licenses](licenses/third_party_licenses.md) documentation.