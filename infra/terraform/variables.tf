variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "ssh_fingerprint" {
  description = "Fingerprint of SSH key registered in DigitalOcean account"
  type        = string
  default     = "4c:16:cc:e0:70:12:c7:db:73:16:de:bb:96:a2:34:06"
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
  default     = "sgp1"
}

variable "github_token" {
  description = "GitHub PAT with repo write access to the supply chain target repo"
  type        = string
  sensitive   = true
}

variable "github_repo" {
  description = "GitHub repo used as supply chain vector (owner/name)"
  type        = string
  default     = "kavienanj/aw_do_webapp"
}
